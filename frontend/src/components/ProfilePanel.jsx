import React, { useRef, useState } from 'react';
import { UserRound } from 'lucide-react';
import { CATEGORIES, blankProfile } from '../api.js';

const LISTS = [['hackathons','Hackathons','Hackathon name - result or role'],['internships','Internships','Role, company, duration'],['experience','Experience','Role, responsibilities, dates'],['certifications','Certifications','Certification name'],['preferred_roles','Preferred roles','Software Engineer Intern'],['projects','Projects','Project name - what you built']];

function SkillRow({s, onChange, onRemove}) {
  const unassessed = s.level == null;
  return <div className="skillrow">
    <input aria-label="Skill name" value={s.skill_name} onChange={e => onChange('skill_name', e.target.value)} placeholder="Skill name"/>
    <select aria-label="Category" value={s.category_code} onChange={e => onChange('category_code', e.target.value)}>{CATEGORIES.map(c => <option key={c}>{c}</option>)}</select>
    <input aria-label="Evidence" value={s.evidence || ''} onChange={e => onChange('evidence', e.target.value)} placeholder="Evidence from resume"/>
    <select aria-label="Confidence" value={s.confidence || 'low'} onChange={e => onChange('confidence', e.target.value)}><option value="high">High confidence</option><option value="medium">Medium confidence</option><option value="low">Low confidence</option></select>
    <label className="level">Level <input type="number" min="1" max="10" placeholder="-" value={s.level ?? ''} onChange={e => { const v = e.target.value; onChange('level', v === '' ? null : Math.max(1, Math.min(10, Math.round(Number(v))))); }}/></label>
    <button className="remove" onClick={onRemove} aria-label="Remove skill">×</button>
    {unassessed && <small className="unassessed">Not assessed - left out of Talent Check, not counted as zero.</small>}
  </div>;
}

export default function ProfilePanel({profile, update, busy, savedId, onSave, onLoad, onReview, review, savedCandidates = [], onSelectCandidate, completeness, onImport}) {
  const importInput = useRef(null);
  const [fileError, setFileError] = useState('');
  const exportProfile = () => {
    const blob = new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `radix-profile-${(profile.name || 'candidate').toLowerCase().replace(/[^a-z0-9]+/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const importProfileFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    setFileError('');
    if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw new Error('Profile JSON must be under 1 MB.');
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('The file must contain a single profile JSON object.');
      if (data.skills != null && !Array.isArray(data.skills)) throw new Error('The skills field must be a list.');
      const safe = { ...blankProfile, ...data };
      safe.skills = (safe.skills || []).filter((x) => x && typeof x === 'object').map((x) => ({
        skill_name: String(x.skill_name || ''), category_code: CATEGORIES.includes(String(x.category_code || '').toUpperCase()) ? String(x.category_code).toUpperCase() : 'OTHER',
        evidence: String(x.evidence || ''), confidence: ['high', 'medium', 'low'].includes(x.confidence) ? x.confidence : 'low',
        level: x.level == null || x.level === '' ? null : (Number.isFinite(Number(x.level)) && Number(x.level) >= 1 && Number(x.level) <= 10 ? Math.round(Number(x.level)) : null),
        source: String(x.source || 'import')
      }));
      for (const key of ['hackathons', 'internships', 'experience', 'certifications', 'preferred_roles', 'projects']) {
        if (!Array.isArray(safe[key])) safe[key] = [];
        safe[key] = safe[key].map((x) => String(x));
      }
      if (typeof onImport === 'function') onImport(safe);
      else for (const key of Object.keys(blankProfile)) update(key, safe[key]);
    } catch (error) {
      setFileError(error.message || 'Could not import this profile JSON.');
    }
  };
  const updateList = (k, text) => update(k, text.split('\n').map(x => x.trim()).filter(Boolean));
  const addSkill = () => update('skills', [...profile.skills, {skill_name: '', category_code: 'COD', evidence: '', confidence: 'low', level: null, source: 'manual'}]);
  const changeSkill = (i, k, v) => update('skills', profile.skills.map((s, n) => n === i ? {...s, [k]: v} : s));
  const assessed = profile.skills.filter(s => s.level != null).length;
  return <section className="panel profile">
    <div className="sectionhead"><div><div className="kicker">ROLE 3</div><h2><UserRound size={22}/> Candidate Profile Builder</h2><p>Review extracted details and add explicit skill levels from 1–10. Levels are never inferred from resume keywords; a blank level means “not assessed”.</p></div>
      <div className="actions"><button className="btn secondary" onClick={onReview} disabled={!!busy} title="Sends curated profile fields/evidence to the configured AI provider for review. Name, email, candidate ID and CV filename are excluded. It will not edit or save your profile.">{busy === 'review' ? 'Reviewing…' : <><UserRound size={15}/> AI profile review</>}</button><button className="btn secondary" onClick={onLoad} disabled={!!busy || !savedId}>{busy === 'load' ? 'Loading…' : 'Load saved profile'}</button><button className="btn secondary" onClick={onSave} disabled={!!busy}>{busy === 'save' ? 'Saving…' : 'Save profile'}</button></div></div>
    <div className="profile-tools">
      <label className="profile-candidate-picker">Saved candidates
        <select aria-label="Saved candidates" value={savedId || ''} disabled={!savedCandidates.length || !!busy} onChange={(e) => onSelectCandidate?.(e.target.value)}>
          <option value="">Select a saved candidate</option>
          {savedCandidates.map((candidate) => <option key={candidate.candidate_id} value={candidate.candidate_id}>{candidate.name} · {candidate.skills_count} skills</option>)}
        </select>
      </label>
      <div className="profile-tools__actions">
        <button type="button" className="btn secondary small" onClick={exportProfile}>Export JSON</button>
        <button type="button" className="btn secondary small" onClick={() => importInput.current?.click()} disabled={!!busy}>Import JSON</button>
        <input ref={importInput} className="sr-only" type="file" accept=".json,application/json" onChange={importProfileFile} />
      </div>
      {completeness && <div className="profile-completeness"><span>Profile completeness</span><strong>{completeness.score}%</strong><small>{completeness.completed_fields}/{completeness.total_fields} checks complete</small><div className="evidence-bar-track"><i style={{ width: `${completeness.score}%` }}/></div></div>}
      {fileError && <p className="profile-import-error" role="alert">{fileError}</p>}
    </div>
    <div className="formgrid">
      <label>Full name<input value={profile.name} onChange={e => update('name', e.target.value)} placeholder="Candidate name"/></label>
      <label>Email<input value={profile.email} onChange={e => update('email', e.target.value)} placeholder="candidate@example.com"/></label>
      <label className="wide">Education<input value={profile.education} onChange={e => update('education', e.target.value)} placeholder="Degree, institution, graduation year"/></label>
    </div>
    <div className="formgrid extras">{LISTS.map(([k, label, ph]) => <label key={k} className={k === 'projects' ? 'wide' : ''}>{label} <small>One per line</small><textarea value={(profile[k] || []).join('\n')} onChange={e => updateList(k, e.target.value)} placeholder={ph}/></label>)}</div>
    {profile.cv_file && <p className="micro">Attached CV: {profile.cv_file}</p>}
    <div className="skillhead"><div><h3>Skills & evidence <span>{profile.skills.length}</span></h3><small>{assessed}/{profile.skills.length} have a level. Talent Check only scores categories that contain a leveled skill.</small></div><button className="btn secondary small" onClick={addSkill}>+ Add skill</button></div>
    {profile.skills.length === 0 ? <div className="empty">Parse a resume or add skills manually to get started.</div> : <div className="skilllist">{profile.skills.map((s, i) => <SkillRow key={i} s={s} onChange={(k, v) => changeSkill(i, k, v)} onRemove={() => update('skills', profile.skills.filter((_, n) => n !== i))}/>)}</div>}
    {review && <section className={`profile-ai-review ${review.status !== 'ready' ? 'profile-ai-review--notice' : ''}`}>
      <div className="profile-ai-review__head"><span className="profile-ai-review__icon"><UserRound size={16}/></span><div><b>AI profile review</b><small>{review.ai_assist?.provider_used ? `${review.ai_assist.provider_used}${review.ai_assist.model_used ? ` · ${review.ai_assist.model_used}` : ''}` : 'Read-only review'}</small></div>{review.ai_assist?.fallback_used && <span className="profile-ai-review__fallback">FALLBACK USED</span>}</div>
      {review.status === 'ready' ? <>
        <p className="profile-ai-review__summary">{review.review?.summary}</p>
        {review.review?.strengths?.length > 0 && <><h4>What is already clear</h4><ul>{review.review.strengths.map((item, i) => <li key={i}>{item}</li>)}</ul></>}
        {review.review?.profile_gaps?.length > 0 && <><h4>Profile improvements</h4><div className="profile-ai-review__gaps">{review.review.profile_gaps.map((item, i) => <article key={`${item.area}-${i}`}><div><b>{item.area}</b><span className={`profile-ai-review__priority profile-ai-review__priority--${item.priority}`}>{item.priority}</span></div><p>{item.issue}</p><small>{item.recommendation}</small></article>)}</div></>}
        {review.review?.skill_reviews?.length > 0 && <><h4>Skill evidence review</h4><div className="profile-ai-review__skills">{review.review.skill_reviews.map((item, i) => <article key={`${item.skill_name}-${i}`}><div><b>{item.skill_name}</b><span>{item.status.replaceAll('_', ' ')}</span></div><p>{item.observation}</p><small>{item.next_step}</small></article>)}</div></>}
        {review.review?.limitations?.length > 0 && <p className="profile-ai-review__limitations">{review.review.limitations.join(' ')}</p>}
        <small className="profile-ai-review__foot">Suggestions only. This review has not edited or saved any profile values.</small>
      </> : <p>{review.message || 'AI review unavailable. The profile remains unchanged.'}</p>}
    </section>}
  </section>;
}
