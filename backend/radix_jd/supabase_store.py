"""Small server-side Supabase REST adapter. Secrets never leave the backend."""
from __future__ import annotations
import os
from typing import Any
import requests

class SupabaseStore:
    def __init__(self, url: str = '', key: str = ''):
        self.url = url.rstrip('/')
        self.key = key

    @classmethod
    def from_env(cls) -> 'SupabaseStore':
        return cls(os.getenv('SUPABASE_URL', ''), os.getenv('SUPABASE_SERVICE_ROLE_KEY', '') or os.getenv('SUPABASE_KEY', ''))

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)

    def _request(self, method: str, table: str, *, params: dict[str, str] | None = None,
                 body: dict[str, Any] | None = None, prefer: str | None = None, timeout: float = 8) -> Any:
        if not self.configured:
            raise RuntimeError('Supabase is not configured')
        headers = {'apikey': self.key, 'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'}
        if prefer: headers['Prefer'] = prefer
        response = requests.request(method, f'{self.url}/rest/v1/{table}', params=params, json=body, headers=headers, timeout=timeout)
        response.raise_for_status()
        if not response.content: return None
        try: return response.json()
        except ValueError: return None

    def check_table(self, table: str, columns: str = '*') -> dict[str, Any]:
        """Probe a table with a read-only REST request; never returns credentials."""
        try:
            self._request('GET', table, params={'select': columns, 'limit': '1'}, timeout=3)
            return {'ok': True, 'table': table}
        except Exception as exc:
            # PostgREST errors can include schema details, but not the API key. Keep the UI concise.
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            return {'ok': False, 'table': table, 'error': f'HTTP {status}' if status else type(exc).__name__}


    @staticmethod
    def _category_code(short_name: str, skill_name: str) -> str | None:
        import re
        code = (short_name or '').strip().upper()
        valid = {'COD','DSA','APTI','COMM','OOD','AI','SQL','SYSD','CLOUD','SWE','NETW','OS'}
        if code in valid:
            return code
        value = re.sub(r'[^a-z0-9]+', ' ', f'{short_name or ""} {skill_name or ""}'.lower()).strip()
        # Specific categories first: e.g. "Object-Oriented Programming" must
        # map to OOD, not COD merely because its name contains "programming".
        aliases = {
            'DSA': ('data structures algorithms','data structure','algorithm'),
            'OOD': ('object oriented','oop','object oriented programming design'),
            'APTI': ('aptitude','problem solving','reasoning'),
            'COMM': ('communication','presentation'),
            'AI': ('artificial intelligence','machine learning','ai native','ai ml'),
            'SYSD': ('system design','system architecture','software architecture'),
            'CLOUD': ('cloud','devops'),
            'SQL': ('sql','database','databases'),
            'SWE': ('software engineering','software development','testing'),
            'NETW': ('networking','computer network','network'),
            'OS': ('operating system','operating systems'),
            'COD': ('coding','programming','programming language'),
        }
        for category, terms in aliases.items():
            if any(term.strip() in value for term in terms):
                return category
        return None

    def list_company_benchmarks(self) -> list[dict[str, Any]]:
        """Read the existing company/skill tables without modifying their schema."""
        companies = self._request('GET', 'companies', params={
            'select': 'company_id,name,short_name', 'order': 'name.asc', 'limit': '1000'
        }) or []
        skillsets = self._request('GET', 'skill_set_master', params={
            'select': 'skill_set_id,skill_set_name,short_name', 'limit': '1000'
        }) or []
        levels: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._request('GET', 'company_skill_levels', params={
                'select': 'company_id,skill_set_id,required_level', 'limit': '1000', 'offset': str(offset)
            }) or []
            levels.extend(page)
            if len(page) < 1000:
                break
            offset += len(page)
            if offset > 20000:
                raise RuntimeError('Company benchmark pagination safety limit exceeded')
        by_skill_id: dict[str, str] = {}
        for skillset in skillsets:
            category = self._category_code(str(skillset.get('short_name') or ''), str(skillset.get('skill_set_name') or ''))
            if category:
                by_skill_id[str(skillset.get('skill_set_id'))] = category
        required_codes = {'COD','DSA','APTI','COMM','OOD','AI','SQL','SYSD','CLOUD','SWE','NETW','OS'}
        levels_by_company: dict[str, dict[str, int]] = {}
        for row in levels:
            company_key = str(row.get('company_id'))
            category = by_skill_id.get(str(row.get('skill_set_id')))
            if not category:
                continue
            try:
                level = int(row.get('required_level'))
            except (TypeError, ValueError):
                continue
            if 1 <= level <= 10:
                levels_by_company.setdefault(company_key, {})[category] = level
        result = []
        for company in companies:
            company_id = str(company.get('company_id'))
            skill_levels = levels_by_company.get(company_id, {})
            if set(skill_levels) != required_codes:
                continue
            result.append({
                'company_id': int(company_id) if company_id.isdigit() else company_id,
                'name': company.get('name') or company.get('short_name') or f'Company {company_id}',
                'short_name': company.get('short_name') or company.get('name') or f'Company {company_id}',
                'skill_levels': skill_levels,
                'levels': [skill_levels[code] for code in ('COD','DSA','APTI','COMM','OOD','AI','SQL','SYSD','CLOUD','SWE','NETW','OS')],
                'source': 'supabase',
            })
        return result

    def insert_jd_result(self, result: dict[str, Any]) -> dict[str, Any]:
        payload = {k: result.get(k) for k in ('source_type','source_file','company','role','skills','extraction_method')}
        rows = self._request('POST', 'jd_analytics_results', body=payload, prefer='return=representation')
        row = rows[0] if isinstance(rows, list) and rows else {}
        return {'saved': True, 'mode': 'supabase', 'id': row.get('id'), 'created_at': row.get('created_at')}

    def get_jd_result(self, jd_id: str) -> dict[str, Any] | None:
        """Fetch one analysed JD by its ``jd_analytics_results.id``. The caller must validate ``jd_id`` first."""
        rows = self._request('GET', 'jd_analytics_results', params={'select': '*', 'id': f'eq.{jd_id}', 'limit': '1'})
        return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None

    def upsert_profile(self, profile: dict[str, Any]) -> None:
        self._request('POST', 'radix_candidate_profiles', params={'on_conflict': 'candidate_id'}, body={
            'candidate_id': profile['candidate_id'], 'profile': profile
        }, prefer='resolution=merge-duplicates,return=minimal')

    def get_profile(self, candidate_id: str) -> dict[str, Any] | None:
        rows = self._request('GET', 'radix_candidate_profiles', params={
            'select': 'profile', 'candidate_id': f'eq.{candidate_id}', 'limit': '1'
        })
        if not isinstance(rows, list) or not rows: return None
        profile = rows[0].get('profile')
        return profile if isinstance(profile, dict) else None

    def list_profiles(self) -> list[dict[str, Any]]:
        rows = self._request('GET', 'radix_candidate_profiles', params={
            'select': 'profile', 'order': 'created_at.desc', 'limit': '100'
        })
        if not isinstance(rows, list):
            return []
        return [row['profile'] for row in rows if isinstance(row, dict) and isinstance(row.get('profile'), dict)]

    def delete_profile(self, candidate_id: str) -> bool:
        rows = self._request('DELETE', 'radix_candidate_profiles', params={
            'candidate_id': f'eq.{candidate_id}', 'select': 'candidate_id'
        }, prefer='return=representation')
        return bool(rows)

    def insert_result(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request('POST', table, body=payload, prefer='return=representation')
        row = rows[0] if isinstance(rows, list) and rows else {}
        return {'saved': True, 'mode': 'supabase', 'id': row.get('id'), 'created_at': row.get('created_at')}
