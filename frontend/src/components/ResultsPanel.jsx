
import React from 'react';
import { BarChart3, GitCompare } from 'lucide-react';

const STATUS = {
  meets_bar: ['Meets bar', 'ok'],
  close_gap: ['Close gap', 'warn'],
  priority_gap: ['Priority gap', 'bad'],
  unassessed: ['Not assessed', 'na']
};

function TalentCard({ t }) {
  const rows = t.skillset_gap || [];

  return (
    <div className="scorecard">
      <div className="scorelabel">COMPANY READINESS · {t.company}</div>
      <div className="score">
        {t.readiness_score ?? '-'}
        <small>{t.readiness_score == null ? '' : '/100'}</small>
      </div>
      <b>{t.readiness_label}</b>
      <small>
        Benchmark: {t.benchmark_source === 'supabase'
          ? 'Supabase company data'
          : 'official hackathon snapshot'}
      </small>
      <div className="bar">
        <span style={{ width: `${t.readiness_score || 0}%` }} />
      </div>
      <small>
        {t.skills_assessed}/12 categories assessed
        {t.readiness_score != null && t.skills_assessed < 12
          ? ` · if the rest were zero: ${t.readiness_floor}`
          : ''}.
        {' '}Unassessed categories are left out, not scored as zero.
      </small>

      <div className="talent-comparison-chart" aria-label="Candidate skill levels compared with company required levels">
        <div className="talent-comparison-chart__head"><h4>Candidate vs company bar</h4><div className="talent-chart-legend"><span><i className="legend-candidate"/> Candidate level</span><span><i className="legend-required"/> Company requirement</span></div></div>
        {rows.map((g) => <div className="talent-comparison-row" key={g.category_code}>
          <span className="talent-comparison-code">{g.category_code}</span>
          <div className="talent-comparison-track" title={`${g.category_code}: candidate ${g.candidate_level ?? 'not assessed'} / company requirement ${g.required_level}`}>
            {g.candidate_level != null && <i className="talent-comparison-candidate" style={{ width: `${g.candidate_level * 10}%` }} />}
            <i className="talent-comparison-required" style={{ width: `${g.required_level * 10}%` }} />
          </div>
          <b>{g.candidate_level == null ? '-' : g.candidate_level}<small> / {g.required_level}</small></b>
        </div>)}
      </div>
      <div className="catlist">
        {rows.map((g) => {
          const [label, tone] = STATUS[g.status] || [g.status, 'na'];

          return (
            <div
              className={`catrow ${tone}`}
              key={g.category_code}
              title={g.explanation}
            >
              <span className="code">{g.category_code}</span>
              <span className="catname">{g.skill_name}</span>
              <span className="lv">
                {g.candidate_level == null ? '-' : g.candidate_level}
                {' / '}{g.required_level}
              </span>
              <span className={`badge ${tone}`}>{label}</span>
              <small className="why">{g.explanation}</small>
            </div>
          );
        })}
      </div>
      <TalentCoach data={t.ai_coaching} />
    </div>
  );
}


function TalentCoach({ data }) {
  if (!data) return null;
  const assist = data.ai_assist || {};
  const coaching = data.coaching || {};

  if (data.status !== 'ready') {
    const title = data.status === 'needs_assessment'
      ? 'Complete a proficiency assessment first'
      : data.status === 'disabled'
        ? 'AI readiness coaching is disabled'
        : 'AI coaching unavailable';
    return (
      <section className="talent-coach talent-coach--notice">
        <div className="talent-coach__heading"><BarChart3 size={16} /><b>{title}</b></div>
        <p>{data.message || 'The deterministic readiness score is still available. Check AI provider configuration if you expected recommendations.'}</p>
      </section>
    );
  }

  return (
    <section className="talent-coach">
      <div className="talent-coach__heading">
        <span className="talent-coach__icon"><BarChart3 size={16} /></span>
        <div><b>AI readiness coach</b><small>{assist.provider_used || 'Configured provider'}{assist.model_used ? ` · ${assist.model_used}` : ''}</small></div>
        {assist.fallback_used && <span className="talent-coach__fallback">FALLBACK USED</span>}
      </div>
      {Number.isFinite(Number(coaching.ai_rating_10)) && (
        <div className="talent-ai-rating" aria-label={`AI readiness rating ${coaching.ai_rating_10} out of 10`}>
          <div className="talent-ai-rating__score">
            <span>AI READINESS RATING</span>
            <strong>{Number(coaching.ai_rating_10).toFixed(1)}<small> / 10</small></strong>
            <div className="talent-ai-rating__track"><i style={{ width: `${Math.max(0, Math.min(100, Number(coaching.ai_rating_10) * 10))}%` }} /></div>
            <small>Advisory estimate · not a hiring decision</small>
          </div>
          <div className="talent-ai-rating__details">
            <div className="talent-ai-rating__meta">
              <b>AI evidence assessment</b>
              <span className={`talent-ai-rating__confidence talent-ai-rating__confidence--${coaching.rating_confidence || 'low'}`}>
                {(coaching.rating_confidence || 'low').toUpperCase()} CONFIDENCE
              </span>
            </div>
            <p>{coaching.rating_rationale || coaching.summary}</p>
            {coaching.rating_evidence?.length > 0 && <ul>{coaching.rating_evidence.map((item, i) => <li key={i}>{item}</li>)}</ul>}
            <small>Deterministic benchmark baseline: {coaching.benchmark_anchor_10 ?? '-'} / 10. AI rating is constrained to within 1.5 points of this baseline. The official readiness score above is unchanged.</small>
          </div>
        </div>
      )}
      <p className="talent-coach__summary">{coaching.summary}</p>
      {coaching.strengths?.length > 0 && <>
        <h5>Strengths supported by assessment</h5>
        <ul className="talent-coach__list">{coaching.strengths.map((x, i) => <li key={i}>{x}</li>)}</ul>
      </>}
      {coaching.priorities?.length > 0 && <>
        <h5>Recommended next actions</h5>
        <div className="talent-coach__priorities">
          {coaching.priorities.map((item) => (
            <article className="talent-coach__priority" key={item.category_code}>
              <div className="talent-coach__priority-top">
                <b>{item.category_code} · {item.category_label}</b>
                <span className={`talent-coach__level talent-coach__level--${item.priority}`}>{item.priority}</span>
              </div>
              <p>{item.action}</p>
              <small><strong>Practice:</strong> {item.practice_task}</small>
              <small><strong>Evidence to add:</strong> {item.evidence_to_add}</small>
              {item.status === 'unassessed' && <small className="talent-coach__caveat">This category is unassessed, not scored as a weakness.</small>}
            </article>
          ))}
        </div>
      </>}
      {coaching.seven_day_plan?.length > 0 && <>
        <h5>Suggested 7-day plan</h5>
        <ol className="talent-coach__list">{coaching.seven_day_plan.map((x, i) => <li key={i}>{x}</li>)}</ol>
      </>}
      {coaching.limitations?.length > 0 && <p className="talent-coach__limitations">{coaching.limitations.join(' ')}</p>}
      <small className="talent-coach__disclaimer">AI rating is advisory and evidence-limited; it does not change the official benchmark score. Curated skill/evidence and project text may be sent to the configured provider; contact identifiers are excluded.</small>
    </section>
  );
}

function MatchCard({ m }) {
  const details = m.match_details || [];
  const matched = details.filter((d) => d.matched);
  const missing = m.gaps || m.recommendations || [];
  const counts = m.counts || {};
  const weightedCoverage = (kind) => {
    const group = details.filter((d) => d.requirement_type === kind);
    const possible = group.reduce((total, d) => total + Number(d.weight || 0), 0);
    const earned = group.reduce((total, d) => total + Number(d.points_earned || 0), 0);
    return { possible, earned, percent: possible ? earned / possible * 100 : null };
  };
  const requiredCoverage = weightedCoverage('required');
  const preferredCoverage = weightedCoverage('preferred');

  return (
    <div className="scorecard">
      <div className="scorelabel">JOB-SPECIFIC MATCH</div>
      <div className="score">
        {m.match_score ?? '-'}
        <small>{m.match_score == null ? '' : '/100'}</small>
      </div>
      <b>{m.status === 'scored' ? 'Skill coverage estimate' : 'Unable to calculate'}</b>
      <div className="bar pink">
        <span style={{ width: `${m.match_score || 0}%` }} />
      </div>
      <small>
        {counts.matched_required ?? 0} required matched ·
        {' '}{counts.missing_required ?? 0} required missing ·
        {' '}JD source: {m.jd_source_file || 'uploaded job description'}
        {m.jd_resolution === 'jd_id' ? ' (saved analysis)' : ''}
      </small>

      <div className="match-weight-breakdown">
        {[['Required', requiredCoverage], ['Preferred', preferredCoverage]].filter(([, group]) => group.possible > 0).map(([label, group]) => <div className="match-weight-row" key={label}>
          <div><b>{label}</b><small>{group.earned.toFixed(2)} / {group.possible.toFixed(2)} weighted points</small></div>
          <div className="match-weight-track"><i style={{ width: `${Math.max(0, Math.min(100, group.percent || 0))}%` }} /></div>
          <strong>{group.percent == null ? 'N/A' : `${group.percent.toFixed(1)}%`}</strong>
        </div>)}
      </div>

      {m.reason && <small className="warn">{m.reason}</small>}

      {m.ai_assist?.applied && (
        <small className="why">
          AI semantic assist used {m.ai_assist.provider_used || 'a configured provider'} to suggest {m.ai_assist.semantic_matches?.length || 0} evidence-grounded equivalence(s). Points are still calculated by the deterministic scorer. Review the matched-with labels below.
        </small>
      )}
      {m.ai_assist?.enabled && !m.ai_assist?.applied && (
        <small className="why">
          AI semantic assist did not add any matches{m.ai_assist.reason ? ` (${m.ai_assist.reason})` : ''}; exact, alias, phrase and fuzzy matching remains active.
        </small>
      )}

      <h4>Missing skills - what to build first</h4>
      {missing.length === 0 ? (
        <small>No gaps: every JD skill was matched.</small>
      ) : (
        <div className="gaps">
          {missing.slice(0, 8).map((g, i) => (
            <div key={i} title={g.why || ''}>
              <span>
                {g.skill}
                <small className="why">{g.why}</small>
                {g.learn_next && <small className="learn-next"><b>Learn next:</b> {g.learn_next.action} <i>{g.learn_next.estimated_effort}</i></small>}
              </span>
              <b>
                {g.priority}
                {g.points_lost != null ? ` · −${g.points_lost} pts` : ''}
              </b>
            </div>
          ))}
        </div>
      )}

      <h4>Matched ({matched.length})</h4>
      <div className="chips">
        {matched.map((d) => (
          <span
            key={d.skill}
            title={`${d.requirement_type} · ${d.match_type}${
              d.matched_with && d.matched_with !== d.skill
                ? ` via “${d.matched_with}”`
                : ''
            }`}
          >
            {d.skill}
            {d.match_type === 'semantic_ai' ? ' (AI-supported)' : d.match_type === 'phrase' ? ' (phrase match)' : d.match_type !== 'exact' ? ` (${d.match_type})` : ''}
          </span>
        ))}
      </div>

      {matched.length > 0 && <>
        <h4>Evidence for matched skills</h4>
        <div className="match-evidence-list">{matched.map((d) => <article key={d.skill}>
          <div><b>{d.skill}</b><span className={`match-type match-type--${d.match_type || 'exact'}`}>{d.match_type || 'exact'}</span></div>
          <p>{d.evidence_quote || 'No evidence quote was supplied in the candidate profile. Review this name-only match before relying on it.'}</p>
          <small>Matched with: {d.matched_with || d.skill} · {d.requirement_type} · {d.evidence_confidence || 'confidence not supplied'}</small>
        </article>)}</div>
      </>}

      {m.fuzzy_matches?.length > 0 && (
        <small>
          Includes {m.fuzzy_matches.length} close-spelling match(es);
          exact-only score {m.exact_only_score}/100.
        </small>
      )}
    </div>
  );
}

export default function ResultsPanel({
  companies,
  companyId,
  setCompanyId,
  busy,
  onTalent,
  onMatch,
  talent,
  match,
  jd,
  mode = 'both'
}) {
  const snap = companies.filter((c) => c.source === 'snapshot');
  const sb = companies.filter((c) => c.source === 'supabase');

  return (
    <section className="panel">
      <div className="sectionhead">
        <div>
          <div className="kicker">
            {mode === 'talent' ? 'ROLE 4' : mode === 'match' ? 'ROLE 5' : 'ROLES 4 + 5'}
          </div>
          <h2>
            {mode === 'talent'
              ? 'Company Readiness'
              : mode === 'match'
                ? 'Job-Specific Skill Match'
                : 'Readiness & Job Match'}
          </h2>
          <p>
            {mode === 'match'
              ? `Skill Matching uses the job description analysed above${jd ? '.' : ' (not analysed yet).' }`
              : 'Choose a company benchmark to assess candidate readiness.'}
          </p>
        </div>

        <label className="company">
          Company
          <select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
            {snap.length > 0 && (
              <optgroup label="Hackathon benchmark snapshot">
                {snap.map((c) => (
                  <option key={c.company_id} value={c.company_id}>{c.short_name}</option>
                ))}
              </optgroup>
            )}
            {sb.length > 0 && (
              <optgroup label="Supabase company benchmarks">
                {sb.map((c) => (
                  <option key={c.company_id} value={c.company_id}>{c.short_name}</option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
      </div>

      <div className="actions">
        {mode !== 'match' && (
          <button className="btn primary" onClick={onTalent} disabled={!!busy}>
            {busy === 'talent' ? 'Calculating…' : <><BarChart3 size={17} /> Run Talent Check</>}
          </button>
        )}
        {mode !== 'talent' && (
          <button className="btn dark" onClick={onMatch} disabled={!!busy || !jd}>
            {busy === 'match' ? 'Matching…' : <><GitCompare size={17} /> Run Skill Matching</>}
          </button>
        )}
      </div>

      <div className="resultgrid">
        {mode !== 'match' && talent && <TalentCard t={talent} />}
        {mode !== 'talent' && match && <MatchCard m={match} />}

        {(mode === 'talent'
          ? !talent
          : mode === 'match'
            ? !match
            : !talent && !match) && (
          <div className="empty wideempty">
            {mode === 'talent'
              ? 'Run Talent Check to view benchmark readiness.'
              : mode === 'match'
                ? (jd
                  ? 'Run Skill Matching to view matched skills and gaps.'
                  : 'Analyse a job description first, then run Skill Matching.')
                : 'Your results will appear here. Save or review the profile, then run an assessment.'}
          </div>
        )}
      </div>
    </section>
  );
}
