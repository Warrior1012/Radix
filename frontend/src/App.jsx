
import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, BarChart3, BriefcaseBusiness,
  Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, Database, GitCompareArrows,
  LayoutDashboard, Menu, ScanText, Settings2, ShieldCheck, UserRound, X,
  ClipboardList, Users, BookOpen, RefreshCw, FileCheck2, Workflow, CircleCheck
} from 'lucide-react';
import { call, blankProfile, companyIdForTalent, companyIdForMatch, getApiBase, setApiBase } from './api.js';
import JdPanel from './components/JdPanel.jsx';
import ResumePanel from './components/ResumePanel.jsx';
import ProfilePanel from './components/ProfilePanel.jsx';
import ResultsPanel from './components/ResultsPanel.jsx';

const STAGES = [
  { id: 'jd-workspace', title: 'JD Analytics', detail: 'Decode the role', icon: BriefcaseBusiness },
  { id: 'resume-workspace', title: 'Resume Parsing', detail: 'Find skill evidence', icon: ScanText },
  { id: 'profile-workspace', title: 'Profile Builder', detail: 'Shape the profile', icon: UserRound },
  { id: 'talent-workspace', title: 'Talent Check', detail: 'Measure readiness', icon: BarChart3 },
  { id: 'match-workspace', title: 'Skill Matching', detail: 'Expose the gaps', icon: GitCompareArrows },
];

function stateFor(i, { jd, resumeParsed, profile, talent, match }) {
  if (i === 0 && jd) return 'complete';
  if (i === 1 && resumeParsed) return 'complete';
  if (i === 2 && profile.skills.length) return 'ready';
  if (i === 3 && talent) return 'complete';
  if (i === 4 && match) return 'complete';
  return 'idle';
}

function SignalMap() {
  return (
    <div className="signal-map" aria-label="Abstract illustration of skills connected to job requirements">
      <div className="signal-map__top">
        <span>SKILL SIGNAL / 01</span>
        <span className="signal-map__live"><i /> SYSTEM MAP</span>
      </div>
      <svg viewBox="0 0 420 300" role="img" aria-hidden="true">
        <defs>
          <pattern id="gridDots" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="#59604c" opacity=".55" />
          </pattern>
        </defs>
        <rect width="420" height="300" fill="url(#gridDots)" />
        <g className="map-lines" fill="none" stroke="#737b62" strokeWidth="1">
          <path d="M32 235 L105 187 L165 210 L239 126 L304 147 L384 58" />
          <path d="M32 80 L105 122 L165 82 L239 126 L304 73 L384 58" strokeDasharray="3 6" opacity=".7" />
          <path d="M32 235 L32 80 M105 187 L105 122 M165 210 L165 82 M239 126 L239 30 M304 147 L304 73 M384 58 L384 237" strokeDasharray="2 7" opacity=".5" />
        </g>
        <g fill="#171914" stroke="#d4f05a" strokeWidth="2">
          <circle cx="32" cy="235" r="7" />
          <circle cx="105" cy="187" r="6" />
          <circle cx="165" cy="210" r="5" />
          <circle cx="239" cy="126" r="10" />
          <circle cx="304" cy="147" r="6" />
          <circle cx="384" cy="58" r="8" />
        </g>
        <circle className="map-pulse" cx="239" cy="126" r="21" fill="none" stroke="#d4f05a" strokeWidth="1" />
        <g fill="#f2efe6" fontFamily="monospace" fontSize="10" letterSpacing="1.3">
          <text x="18" y="259">COD</text>
          <text x="89" y="211">DSA</text>
          <text x="148" y="235">SWE</text>
          <text x="255" y="116">CORE</text>
          <text x="286" y="169">CLOUD</text>
          <text x="358" y="42">AI</text>
        </g>
        <path d="M18 278 H402" stroke="#4b5142" strokeWidth="1" />
        <path d="M18 278 H125" stroke="#d4f05a" strokeWidth="2" />
        <g fill="#8f9682" fontFamily="monospace" fontSize="8" letterSpacing="1">
          <text x="18" y="293">INPUT</text>
          <text x="199" y="293">EVIDENCE</text>
          <text x="351" y="293">FIT</text>
        </g>
      </svg>
      <div className="signal-map__foot">
        <span>01 / REQUIREMENTS</span>
        <ArrowDownRight size={16} />
        <span>05 / READINESS</span>
      </div>
    </div>
  );
}

function MetricSignal({ icon: Icon, label, value, detail, tone = 'neutral' }) {
  return (
    <div className={`signal-stat signal-stat--${tone}`}>
      <div className="signal-stat__icon"><Icon size={16} /></div>
      <div className="signal-stat__body">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
      <span className="signal-stat__mark" aria-hidden="true" />
    </div>
  );
}

function EvidenceDashboard({ evaluation, savedCandidates, matrix, jdStats, jd, loading, onRefresh, onLoadMatrix }) {
  const metrics = evaluation?.metrics;
  const categories = Object.entries(jdStats?.category_counts || {}).sort((a, b) => b[1] - a[1]);
  const maxCategory = Math.max(1, ...categories.map(([, value]) => Number(value) || 0));
  const matrixRows = matrix?.matrix || [];
  const matrixCompanies = matrixRows[0]?.results?.map((r) => ({ id: r.company_id, name: r.company })) || [];
  const percent = (value) => Number.isFinite(value) ? `${Math.round(value * 100)}%` : 'Not available';

  return (
    <section className="module-screen evidence-screen">
      <div className="screen-heading">
        <div className="kicker">QUALITY / REPRODUCIBILITY</div>
        <h1>Evidence & evaluation</h1>
        <p>Only measured results from saved profiles, analysed JDs and a team-approved evaluation run appear here. Missing evidence is shown as unavailable, never as a zero score.</p>
      </div>

      <div className="evidence-section">
        <div className="evidence-section__head">
          <div><div className="kicker">01 / EXTRACTION QUALITY</div><h2>Evaluation report</h2></div>
          <button className="btn btn-quiet" onClick={onRefresh} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''}/>{loading ? 'Refreshing…' : 'Refresh evidence'}</button>
        </div>
        {evaluation?.available && ['ready', 'partial'].includes(evaluation.status) && metrics ? (
          <>
            <div className="evidence-metrics">
              {[['Precision', metrics.precision], ['Recall', metrics.recall], ['F1', metrics.f1], ['Requirement accuracy', metrics.requirement_type_accuracy]].map(([label, value]) => (
                <div className="evidence-metric" key={label}><span>{label}</span><strong>{value == null ? 'Not available' : percent(value)}</strong></div>
              ))}
            </div>
            {evaluation.status === 'partial' && <div className="evidence-partial-warning"><AlertTriangle size={16}/><span><b>Partial evaluation, not the final benchmark.</b> {evaluation.reason || 'Some official documents or reviewed annotations are still missing.'}</span></div>}
            <div className="evidence-report-note">{evaluation.documents_scored ?? 0} document variants scored · {evaluation.requests_succeeded ?? 0} extraction requests succeeded. Dataset coverage: {evaluation.coverage?.document_variants_scored ?? 0}/{evaluation.coverage?.document_variants_expected ?? 'N/A'} official PDF/DOCX variants.</div>
            {Array.isArray(evaluation.documents) && evaluation.documents.length > 0 && (
              <div className="evidence-table-wrap"><table className="evidence-table"><thead><tr><th>Document</th><th>Format</th><th>Precision</th><th>Recall</th><th>F1</th><th>Latency</th><th>LLM calls</th></tr></thead><tbody>
                {evaluation.documents.map((row, i) => <tr key={`${row.document_id}-${row.format}-${i}`}><td>{row.label || row.document_id}</td><td>{String(row.format || '').toUpperCase()}</td><td>{row.metrics?.precision == null ? 'N/A' : percent(row.metrics.precision)}</td><td>{row.metrics?.recall == null ? 'N/A' : percent(row.metrics.recall)}</td><td>{row.metrics?.f1 == null ? 'N/A' : percent(row.metrics.f1)}</td><td>{row.runtime_ms == null ? 'N/A' : `${row.runtime_ms} ms`}</td><td>{row.model_calls == null ? 'N/A' : row.model_calls}</td></tr>)}
              </tbody></table></div>
            )}
          </>
        ) : (
          <div className="evidence-empty">
            <FileCheck2 size={23}/>
            <div><b>Official evaluation metrics are not available yet.</b><p>{evaluation?.message || evaluation?.reason || 'Run the evaluation harness with official sample documents and team-authored, reviewed ground truth.'}</p><small>Required input: official 6 JD + 4 resume files in PDF/DOCX and manually approved skill annotations. Synthetic test files are not substituted.</small></div>
          </div>
        )}
      </div>

      <div className="evidence-grid">
        <section className="evidence-section">
          <div className="evidence-section__head"><div><div className="kicker">02 / REAL JD OUTPUT</div><h2>JD skill distribution</h2></div></div>
          {jd && jdStats ? <>
            <div className="evidence-jd-meta"><b>{jd.role || jd.source_file}</b><span>{jdStats.total_skills} extracted skills</span></div>
            <div className="evidence-split"><span>Required <b>{jdStats.required}</b></span><span>Preferred <b>{jdStats.preferred}</b></span><span>Model calls <b>{jdStats.model_calls ?? 'N/A'}</b></span><span>Runtime <b>{jdStats.runtime_ms == null ? 'N/A' : `${jdStats.runtime_ms} ms`}</b></span></div>
            {categories.length ? <div className="evidence-bars">{categories.map(([code, count]) => <div className="evidence-bar-row" key={code}><span>{code}</span><div className="evidence-bar-track"><i style={{ width: `${Math.max(4, (Number(count) / maxCategory) * 100)}%` }}/></div><b>{count}</b></div>)}</div> : <p className="evidence-muted">No category counts in this JD result.</p>}
            <small className="evidence-foot">Counts come from the currently analysed JD. {jdStats.cache_hit ? 'The extraction was served from content cache.' : 'The result was freshly processed.'}</small>
          </> : <div className="evidence-empty"><BarChart3 size={22}/><div><b>No analysed JD in this session.</b><p>Run JD Analytics and return here to inspect its category counts.</p></div></div>}
        </section>

        <section className="evidence-section">
          <div className="evidence-section__head"><div><div className="kicker">03 / SAVED CANDIDATES</div><h2>Profile completeness</h2></div><span className="evidence-count">{savedCandidates.length} saved</span></div>
          {savedCandidates.length ? <div className="candidate-evidence-list">{savedCandidates.map((candidate) => <div className="candidate-evidence-row" key={candidate.candidate_id}><div className="candidate-evidence-avatar"><Users size={15}/></div><div className="candidate-evidence-copy"><b>{candidate.name || 'Unnamed candidate'}</b><small>{candidate.skills_count ?? 0} skills · {candidate.candidate_id}</small><div className="evidence-bar-track"><i style={{ width: `${candidate.completeness?.score || 0}%` }}/></div></div><strong>{candidate.completeness?.score ?? '-'}%</strong></div>)}</div> : <div className="evidence-empty"><Users size={22}/><div><b>No saved profiles to compare yet.</b><p>Save real candidate profiles in Profile Builder. The matrix below will only use saved candidates.</p></div></div>}
        </section>
      </div>

      <section className="evidence-section">
        <div className="evidence-section__head"><div><div className="kicker">04 / CANDIDATE × COMPANY</div><h2>Readiness comparison matrix</h2><p>Calculated using the saved profile and current 12-category company benchmark snapshot.</p></div><button className="btn btn-quiet" onClick={onLoadMatrix} disabled={loading || savedCandidates.length === 0}><RefreshCw size={15}/> Recalculate matrix</button></div>
        {matrix?.error ? <div className="evidence-empty"><AlertTriangle size={22}/><div><b>Matrix could not be loaded.</b><p>{matrix.error}</p></div></div> : matrixRows.length && matrixCompanies.length ? <div className="evidence-table-wrap"><table className="evidence-table evidence-table--matrix"><thead><tr><th>Candidate</th>{matrixCompanies.map((c) => <th key={c.id}>{c.name}</th>)}</tr></thead><tbody>{matrixRows.map((row) => <tr key={row.candidate_id}><th>{row.candidate_name || row.candidate_id}</th>{matrixCompanies.map((c) => { const result = row.results?.find((r) => String(r.company_id) === String(c.id)); return <td key={c.id}><strong>{result?.readiness_score == null ? 'Not assessed' : `${result.readiness_score}/100`}</strong><small>{result?.skills_assessed ?? 0}/12 categories</small><small>{result?.readiness_verdict || result?.readiness_label || ''}</small></td>; })}</tr>)}</tbody></table></div> : <div className="evidence-empty"><BarChart3 size={22}/><div><b>Readiness matrix needs saved candidates.</b><p>Save one or more profiles, then recalculate. No candidate values are pre-populated or mocked.</p></div></div>}
      </section>
    </section>
  );
}

function AboutPrivacyPage() {
  return (
    <section className="module-screen about-screen">
      <div className="screen-heading"><div className="kicker">PROJECT NOTES / TRANSPARENCY</div><h1>About & privacy</h1><p>How RADIX Talent Match processes documents, uses AI, and interprets assessment results.</p></div>
      <div className="about-grid">
        <article className="about-card"><BookOpen size={20}/><h2>What the scores mean</h2><p>Talent Check compares explicitly levelled candidate skills with a company benchmark. Unassessed categories are excluded from the readiness score. Skill Matching compares the JD requirements with candidate skill evidence.</p><p>These are guidance signals, not hiring recommendations or a substitute for human review.</p></article>
        <article className="about-card"><ShieldCheck size={20}/><h2>AI and data handling</h2><p>Uploaded JD/resume text may be sent to the AI provider configured in the backend for extraction. Optional profile review and readiness coaching send curated skill/evidence fields; identifiers are excluded by those specific features.</p><p>Use synthetic or consented sample data for demos. Do not upload confidential personal information unless your team is authorised to process it.</p></article>
        <article className="about-card"><Database size={20}/><h2>Storage</h2><p>When Supabase is configured, supported records are stored there using the backend service role. Otherwise profiles and JD results may be stored locally on the backend machine or be available only for the current process, depending on the module.</p><p>Keep the backend .env private and never put provider keys in frontend files.</p></article>
        <article className="about-card"><AlertTriangle size={20}/><h2>Limitations</h2><p>Model outputs can omit skills or misunderstand layout. Text-based PDF/DOCX extraction is supported; image-only scanned PDFs may require OCR and are not guaranteed to work. Review extracted evidence before relying on any result.</p><p>Evaluation metrics remain unavailable until official documents and independently reviewed ground-truth annotations are provided.</p></article>
        <article className="about-card"><BookOpen size={20}/><h2>Terms of use</h2><p>Use RADIX Talent Match for demonstration, learning and decision support only. Verify extracted skills and proficiency levels with the candidate before relying on a score.</p><p>Do not use the tool as the sole basis for hiring, rejection or other high-impact decisions. You are responsible for having permission to upload documents and for following your institution's and data-provider's rules.</p></article>
      </div>
    </section>
  );
}

function StepRail({ state, onNavigate }) {
  return (
    <div className="step-rail" aria-label="Five-step workflow">
      {STAGES.map((s, i) => {
        const status = stateFor(i, state);
        const Icon = s.icon;
        return (
          <button className={`step-tile step-tile--${status}`} key={s.id} onClick={() => onNavigate(s.id)}>
            <span className="step-tile__num">0{i + 1}</span>
            <span className="step-tile__icon">{status === 'complete' ? <Check size={16} /> : <Icon size={16} />}</span>
            <span className="step-tile__copy"><b>{s.title}</b><small>{s.detail}</small></span>
            <ChevronRight className="step-tile__arrow" size={15} />
          </button>
        );
      })}
    </div>
  );
}

function FlowDashboard({ state, connected, busy, jdFile, resumeFile, onNavigate, onRunWorkflow }) {
  const steps = [
    { id: 'jd-workspace', title: 'Analyse job requirements', short: 'JD ANALYTICS', detail: jdFile ? `Selected: ${jdFile.name}` : 'Upload a PDF or DOCX job description.', icon: BriefcaseBusiness, ready: Boolean(jdFile) },
    { id: 'resume-workspace', title: 'Extract candidate evidence', short: 'RESUME PARSING', detail: resumeFile ? `Selected: ${resumeFile.name}` : 'Upload a PDF or DOCX resume.', icon: ScanText, ready: Boolean(resumeFile) },
    { id: 'profile-workspace', title: 'Review and save profile', short: 'PROFILE BUILDER', detail: state.profile?.skills?.length ? `${state.profile.skills.length} skill records in the current profile.` : 'Review extracted information and confirm levels before saving.', icon: UserRound, ready: Boolean(state.profile?.skills?.length) },
    { id: 'talent-workspace', title: 'Measure benchmark readiness', short: 'TALENT CHECK', detail: state.talent ? 'Most recent benchmark result is available.' : 'Calculate readiness against a selected company benchmark.', icon: BarChart3, ready: Boolean(state.talent) },
    { id: 'match-workspace', title: 'Compare to this job', short: 'SKILL MATCHING', detail: state.match ? 'Most recent JD match result is available.' : 'Match evidence against required and preferred JD skills.', icon: GitCompareArrows, ready: Boolean(state.match) },
  ];
  const completed = steps.filter((step, index) => {
    const status = stateFor(index, state);
    return status === 'complete' || status === 'ready';
  }).length;
  const inputsReady = Boolean(jdFile && resumeFile && connected);

  return (
    <section className="module-screen flow-screen">
      <div className="flow-hero">
        <div className="flow-hero__copy">
          <div className="kicker"><span className="flow-kicker-dot" /> ORCHESTRATION / LIVE WORKSPACE</div>
          <h1>One candidate.<br /><em>Five connected stages.</em></h1>
          <p>Move through each role-specific dashboard or run the full sequence from one place. Every stage receives the previous stage's real output; missing evidence remains visible instead of being fabricated.</p>
          <div className="flow-hero__actions">
            <button className="btn btn-primary" disabled={!inputsReady || Boolean(busy)} onClick={onRunWorkflow}>{busy === 'workflow' ? <><RefreshCw className="spin" size={15}/> Workflow running</> : <>Run end-to-end flow <ArrowRight size={16}/></>}</button>
            <span className={`flow-api-state ${connected ? 'is-connected' : ''}`}><i />{connected ? 'API REACHABLE' : 'BACKEND DISCONNECTED'}</span>
          </div>
        </div>
        <div className="flow-art" aria-label="Animated five-stage pipeline graphic">
          <div className="flow-art__meta"><span>RADIX PIPELINE / 05</span><span>DATA, NOT DECORATION</span></div>
          <svg viewBox="0 0 520 210" role="img" aria-hidden="true">
            <path className="flow-art__path flow-art__path--base" d="M32 106 H488" />
            <path className="flow-art__path flow-art__path--active" d="M32 106 H488" />
            {steps.map((step, i) => {
              const x = 32 + i * 114;
              const done = stateFor(i, state) === 'complete' || stateFor(i, state) === 'ready';
              return <g key={step.id} className={`flow-art__node ${done ? 'is-done' : ''}`}>
                <circle cx={x} cy="106" r="19" />
                <circle className="flow-art__ring" cx={x} cy="106" r="27" />
                <text x={x} y="111" textAnchor="middle">0{i + 1}</text>
                <text className="flow-art__label" x={x} y="153" textAnchor="middle">{['JD','RESUME','PROFILE','TALENT','MATCH'][i]}</text>
                <rect className="flow-art__tick" x={x - 3} y="70" width="6" height="6" />
              </g>;
            })}
          </svg>
          <div className="flow-art__footer"><span>INPUT VALIDATION</span><span>PROFILE HAND-OFF</span><span>EXPLAINABLE OUTPUT</span></div>
        </div>
      </div>

      <div className="flow-progress-card">
        <div className="flow-progress-card__label"><span>WORKFLOW CHECKPOINTS</span><b>{completed}/5</b></div>
        <div className="flow-progress-track"><i style={{ width: `${completed / 5 * 100}%` }} /></div>
        <div className="flow-progress-card__foot"><span>Progress uses current session outputs, not assumed completion.</span><span>{completed === 5 ? 'ALL OUTPUTS PRESENT' : 'IN PROGRESS'}</span></div>
      </div>

      <div className="flow-step-list">
        {steps.map((step, i) => {
          const Icon = step.icon;
          const status = stateFor(i, state);
          return <article className={`flow-step-card flow-step-card--${status}`} key={step.id} style={{ '--flow-delay': `${i * 70}ms` }}>
            <div className="flow-step-card__rail"><span>{String(i + 1).padStart(2, '0')}</span><i /></div>
            <div className="flow-step-card__icon"><Icon size={18}/></div>
            <div className="flow-step-card__main"><div className="flow-step-card__kicker">{step.short}</div><h2>{step.title}</h2><p>{step.detail}</p></div>
            <div className={`flow-step-status ${step.ready ? 'is-ready' : ''}`}>{step.ready ? <><CircleCheck size={14}/> OUTPUT PRESENT</> : <><Clock3 size={13}/> NOT RUN</>}</div>
            <button className="btn btn-quiet flow-step-card__button" onClick={() => onNavigate(step.id)}>Open dashboard <ArrowRight size={14}/></button>
          </article>;
        })}
      </div>
      <div className="flow-integrity-note"><ShieldCheck size={17}/><div><b>Integrity guardrails</b><p>Talent Check uses explicit proficiency levels only. Skill Matching can use evidence-grounded AI equivalences, but the deterministic scorer owns the score. Provider failures appear as unavailable and do not become fake zeros or fake success.</p></div></div>
    </section>
  );
}

function BackendSettings({ open, onClose, current, onSave }) {
  const [draft, setDraft] = useState(current);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setDraft(current);
      setError('');
    }
  }, [open, current]);

  if (!open) return null;

  const submit = (e) => {
    e.preventDefault();
    try {
      onSave(setApiBase(draft));
      onClose();
    } catch (err) {
      setError(err.message || 'Could not save this URL.');
    }
  };

  return (
    <div className="modal-scrim" role="presentation" onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <div className="settings-modal__head">
          <div className="settings-modal__icon"><Settings2 size={20} /></div>
          <button className="icon-button" onClick={onClose} aria-label="Close settings"><X size={18} /></button>
        </div>
        <div className="kicker">CONNECTION / CONFIGURATION</div>
        <h2 id="settings-title">Point to your backend.</h2>
        <p>Use the local FastAPI service on your laptop. Your AI key and Supabase service-role key stay in <code>backend/.env</code>, never in this browser.</p>
        <form onSubmit={submit}>
          <label className="settings-label" htmlFor="api-base">Backend base URL</label>
          <input id="api-base" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="http://127.0.0.1:8000" autoFocus />
          {error && <p className="settings-error" role="alert">{error}</p>}
          <div className="settings-modal__actions">
            <button type="button" className="btn btn-quiet" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Save and reconnect <ArrowRight size={16} /></button>
          </div>
        </form>
        <div className="settings-note"><ShieldCheck size={15} /> Stored locally in this browser only.</div>
      </section>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [integrations, setIntegrations] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [savedCandidates, setSavedCandidates] = useState([]);
  const [evaluation, setEvaluation] = useState(null);
  const [readinessMatrix, setReadinessMatrix] = useState(null);
  const [jdStats, setJdStats] = useState(null);
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [profileCompleteness, setProfileCompleteness] = useState(null);
  const [companyId, setCompanyId] = useState('78');
  const [profile, setProfile] = useState(blankProfile);
  const [profileReview, setProfileReview] = useState(null);
  const [jd, setJd] = useState(null);
  const [resumeResult, setResumeResult] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);
  const [resumeParsed, setResumeParsed] = useState(false);
  const [savedId, setSavedId] = useState(() => {
    try { return window.localStorage.getItem('radix-candidate-id') || ''; }
    catch { return ''; }
  });
  const [talent, setTalent] = useState(null);
  const [match, setMatch] = useState(null);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiBase, setApiBaseState] = useState(getApiBase);
  const [refreshKey, setRefreshKey] = useState(0);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [activeNav, setActiveNav] = useState('overview');

  const refreshConnections = useCallback(async () => {
    setHealth(null);
    setIntegrations(null);

    const [h, s, c] = await Promise.allSettled([
      call('/api/health'),
      call('/api/integrations/status'),
      call('/api/companies')
    ]);

    setHealth(h.status === 'fulfilled' ? h.value : {
      status: 'offline',
      error: h.reason?.message || 'API offline'
    });
    setIntegrations(s.status === 'fulfilled' ? s.value : null);

    if (c.status === 'fulfilled') {
      const list = Array.isArray(c.value) ? c.value : (c.value?.companies || []);
      setCompanies(list);
      setCompanyId((current) =>
        list.some((company) => String(company.company_id) === String(current))
          ? current
          : (list[0] ? String(list[0].company_id) : '')
      );
    } else {
      setCompanies([]);
    }
  }, []);

  const refreshProfiles = useCallback(async () => {
    try {
      const data = await call('/api/profiles');
      const rows = data.profiles || [];
      setSavedCandidates(rows);
      return rows;
    } catch {
      setSavedCandidates([]);
      return [];
    }
  }, []);

  const refreshEvidence = useCallback(async () => {
    setEvidenceBusy(true);
    setReadinessMatrix(null);
    try {
      const [evalResult, profileResult] = await Promise.allSettled([
        call('/api/eval/latest'),
        call('/api/profiles')
      ]);
      if (evalResult.status === 'fulfilled') setEvaluation(evalResult.value);
      else setEvaluation({ available: false, status: 'unavailable', message: evalResult.reason?.message || 'Evaluation report could not be loaded.' });
      let candidates = [];
      if (profileResult.status === 'fulfilled') {
        candidates = profileResult.value.profiles || [];
        setSavedCandidates(candidates);
      }
      let companyRows = companies;
      if (!companyRows.length) {
        try {
          const c = await call('/api/companies');
          companyRows = Array.isArray(c) ? c : (c.companies || []);
          setCompanies(companyRows);
        } catch { companyRows = []; }
      }
      const candidateIds = candidates.map((p) => p.candidate_id).filter(Boolean).slice(0, 50);
      const companyIds = companyRows.filter((c) => c.source === 'snapshot').map((c) => c.company_id);
      if (candidateIds.length && companyIds.length) {
        try {
          const result = await call('/api/analytics/matrix', { method: 'POST', json: { candidate_ids: candidateIds, company_ids: companyIds } });
          setReadinessMatrix(result);
        } catch (error) {
          setReadinessMatrix({ error: error.message || 'Matrix could not be loaded.' });
        }
      } else {
        setReadinessMatrix({ matrix: [], companies_count: companyIds.length, candidates_count: candidateIds.length });
      }
    } finally {
      setEvidenceBusy(false);
    }
  }, [companies]);

  useEffect(() => {
    refreshConnections();
    refreshProfiles();
  }, [refreshKey, refreshConnections, refreshProfiles]);

  useEffect(() => {
    if (!jd?.jd_id) {
      setJdStats(null);
      return;
    }
    let cancelled = false;
    call('/api/jd/stats/' + encodeURIComponent(jd.jd_id))
      .then((data) => { if (!cancelled) setJdStats(data); })
      .catch(() => { if (!cancelled) setJdStats(null); });
    return () => { cancelled = true; };
  }, [jd?.jd_id]);

  const navigate = (id) => {
    if (id === 'settings') {
      setSettingsOpen(true);
      return;
    }
    setActiveNav(id);
    setMobileNavOpen(false);
    setNotice('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (id === 'evidence-workspace') refreshEvidence();
  };

  const update = (key, value) => { setProfile((p) => ({ ...p, [key]: value })); setProfileReview(null); setTalent(null); setMatch(null); setProfileCompleteness(null); };
  const withId = (p) => ({ ...p, candidate_id: p.candidate_id || savedId || null });

  async function run(name, fn) {
    setBusy(name);
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setNotice(e.message || 'Something went wrong.');
    } finally {
      setBusy('');
    }
  }

  const analyseJd = () => run('jd', async () => {
    if (!jdFile) throw new Error('Choose a job description file first.');

    const form = new FormData();
    form.append('file', jdFile);
    const data = await call('/api/analyze-jd', { method: 'POST', form }, 'JD analysis failed');

    setJd(data);
    setMatch(null);

    const isDemo = /demo_keyword_fallback/i.test([
      data.processing_path,
      data.analysis_meta?.processing_path,
      data.extraction_method
    ].filter(Boolean).join(' '));

    setNotice(`Job description analysed using ${data.extraction_method || 'the configured extractor'}.${isDemo ? ' DEMO MODE: keyword-only results, not AI extraction.' : ''} Review the extracted requirements below.`);
  });

  const parseResume = () => run('resume', async () => {
    if (!resumeFile) throw new Error('Choose a resume file first.');

    const form = new FormData();
    form.append('file', resumeFile);
    const data = await call('/api/parse-resume', { method: 'POST', form }, 'Resume parsing failed');

    const merged = await call('/api/profile/merge-resume', {
      method: 'POST',
      json: { profile: withId(profile), parsed: data.profile }
    }, 'Could not merge the parsed resume into your profile');

    setProfile(merged.profile);
    setProfileReview(null);
    setResumeResult(data);
    setResumeParsed(true);

    const report = merged.report || {};
    const kept = (report.kept_user_fields || []).length;
    const isDemo = /demo_keyword_fallback/i.test([
      data.processing_path,
      data.extraction_method
    ].filter(Boolean).join(' '));

    const aiMeta = data.ai_metadata || {};
    const modelNote = aiMeta.model_used ? ` Model: ${aiMeta.model_used}${aiMeta.fallback_used ? ' (fallback provider)' : ''}.` : '';
    const failedNote = aiMeta.failed?.length ? ` Earlier provider attempt(s) failed: ${aiMeta.failed.map((x) => `${x.target} (${x.kind})`).join(', ')}.` : '';
    setNotice(`Resume parsed using ${data.extraction_method || 'the configured extractor'}.${modelNote} Merged ${report.skills_added || 0} new skill(s) into your profile${kept ? `; preserved your edits to ${report.kept_user_fields.join(', ')}` : ''}.${isDemo ? ' DEMO MODE: keyword-only results, not AI extraction.' : ''}${failedNote} Review before saving.`);
  });

  const saveProfile = () => run('save', async () => {
    const data = await call('/api/profile', { method: 'POST', json: withId(profile) }, 'Save failed');
    setProfile(data.profile);
    setProfileReview(null);
    setProfileCompleteness(data.completeness || null);
    setSavedId(data.profile.candidate_id);

    try {
      window.localStorage.setItem('radix-candidate-id', data.profile.candidate_id);
    } catch { /* storage blocked */ }

    await refreshProfiles();
    setNotice(data.storage === 'supabase'
      ? 'Profile saved to Supabase.'
      : 'Profile saved to a local JSON file on the backend machine. Configure Supabase for hosted persistence.');
  });

  const loadProfile = () => run('load', async () => {
    if (!savedId) throw new Error('No saved profile ID in this browser yet. Save a profile first.');

    const loaded = await call('/api/profile/' + encodeURIComponent(savedId), {}, 'Load failed');
    setProfile(loaded);
    setProfileReview(null);
    setProfileCompleteness(savedCandidates.find((x) => x.candidate_id === savedId)?.completeness || null);
    setTalent(null);
    setMatch(null);
    setNotice('Saved candidate profile loaded. Previous assessment results were cleared.');
  });

  const importProfileData = (imported) => {
    // Imported JSON becomes a new unsaved candidate by default, avoiding accidental overwrite.
    const next = { ...blankProfile, ...imported, candidate_id: null };
    setProfile(next);
    setSavedId('');
    setProfileCompleteness(null);
    setProfileReview(null);
    setTalent(null);
    setMatch(null);
    try { window.localStorage.removeItem('radix-candidate-id'); } catch { /* storage blocked */ }
    setNotice('Profile JSON imported into the form. Review it, then save to create a new candidate record.');
  };

  const selectResumeFile = (file) => {
    setResumeFile(file);
    setResumeResult(null);
    setResumeParsed(false);
  };

  const changeCompany = (id) => {
    setCompanyId(id);
    setTalent(null);
    setMatch(null);
  };

  const selectJdFile = (file) => {
    setJdFile(file);
    setJd(null);
    setJdStats(null);
    setMatch(null);
  };

  const selectSavedCandidate = (candidateId) => run('select-profile', async () => {
    if (!candidateId) return;
    const loaded = await call('/api/profile/' + encodeURIComponent(candidateId), {}, 'Load candidate failed');
    setProfile(loaded);
    setSavedId(candidateId);
    setProfileReview(null);
    setTalent(null);
    setMatch(null);
    setProfileCompleteness(savedCandidates.find((x) => x.candidate_id === candidateId)?.completeness || null);
    try { window.localStorage.setItem('radix-candidate-id', candidateId); } catch { /* storage blocked */ }
    setNotice(`Loaded saved candidate: ${loaded.name || candidateId}. Assessment results cleared so stale scores are not reused.`);
  });

  const reviewProfile = () => run('review', async () => {
    const data = await call('/api/profile-review', {
      method: 'POST', json: withId(profile)
    }, 'AI profile review failed');
    setProfileReview(data);
    setNotice(data.status === 'ready'
      ? `AI profile review completed using ${data.ai_assist?.provider_used || 'a configured provider'}. No profile fields were changed.`
      : (data.message || 'AI profile review is unavailable. Your profile was not changed.'));
  });

  const runTalentAndCoach = async (profilePayload, selectedCompanyId, existingResult = null) => {
    const request = {
      profile: profilePayload,
      company_id: companyIdForTalent(selectedCompanyId)
    };
    const data = existingResult || await call('/api/talent-check', {
      method: 'POST', json: request
    }, 'Talent Check failed');

    // Coaching is supplementary: provider failure must never discard the deterministic score.
    let coaching;
    try {
      coaching = await call('/api/talent-coach', {
        method: 'POST', json: request
      }, 'AI readiness coaching failed');
    } catch (e) {
      coaching = {
        status: 'unavailable',
        message: e?.message || 'AI coaching was unavailable. The deterministic Talent Check score remains valid.'
      };
    }
    return { ...data, ai_coaching: coaching };
  };

  const runTalent = () => run('talent', async () => {
    const data = await runTalentAndCoach(withId(profile), companyId);
    setTalent(data);
    setNotice(data.ai_coaching?.status === 'ready'
      ? `Talent Check completed. AI readiness actions generated using ${data.ai_coaching.ai_assist?.provider_used || 'a configured provider'}.`
      : `Talent Check completed. ${data.ai_coaching?.message || 'AI coaching was not available; the benchmark score is unchanged.'}`);
  });

  const runMatch = () => run('match', async () => {
    if (!jd) throw new Error('Analyse a job description first.');

    const job = {
      job_id: jd.jd_id || 'uploaded-jd',
      source_file: jd.source_file,
      company_id: companyIdForMatch(companyId),
      required_skills: jd.required_skills || jd.skills?.filter((s) => s.requirement_type === 'required') || [],
      preferred_skills: jd.preferred_skills || jd.skills?.filter((s) => s.requirement_type === 'preferred') || []
    };

    const data = await call('/api/skill-match', {
      method: 'POST',
      json: { profile: withId(profile), job, jd_id: jd.jd_id || undefined }
    }, 'Skill Matching failed');

    setMatch(data);
  });

  const runFullWorkflow = () => run('workflow', async () => {
    if (!jdFile) throw new Error('First open JD Analytics and upload a job description.');
    if (!resumeFile) throw new Error('First open Resume Parsing and upload a candidate resume.');
    if (!companyId) throw new Error('No company benchmark is available. Check the backend connection.');

    setNotice('Workflow running: analysing the job description…');
    const jdForm = new FormData();
    jdForm.append('file', jdFile);

    const jdData = await call('/api/analyze-jd', { method: 'POST', form: jdForm }, 'JD analysis failed');
    setJd(jdData);
    setMatch(null);

    setNotice('Workflow running: parsing the resume…');
    const resumeForm = new FormData();
    resumeForm.append('file', resumeFile);

    const resumeData = await call('/api/parse-resume', { method: 'POST', form: resumeForm }, 'Resume parsing failed');
    const merged = await call('/api/profile/merge-resume', {
      method: 'POST',
      json: { profile: withId(profile), parsed: resumeData.profile }
    }, 'Could not merge parsed resume');

    const mergedProfile = merged.profile;
    setProfile(mergedProfile);
    setProfileReview(null);
    setResumeResult(resumeData);
    setResumeParsed(true);

    setNotice('Workflow running: saving candidate profile…');
    const saved = await call('/api/profile', {
      method: 'POST',
      json: { ...mergedProfile, candidate_id: mergedProfile.candidate_id || savedId || null }
    }, 'Profile save failed');

    setProfile(saved.profile);
    setProfileCompleteness(saved.completeness || null);
    setSavedId(saved.profile.candidate_id);

    try {
      window.localStorage.setItem('radix-candidate-id', saved.profile.candidate_id);
    } catch { /* storage blocked */ }
    await refreshProfiles();

    setNotice('Workflow running: calculating company readiness…');
    const talentProfile = { ...saved.profile, candidate_id: saved.profile.candidate_id };
    const basicTalentData = await call('/api/talent-check', {
      method: 'POST',
      json: { profile: talentProfile, company_id: companyIdForTalent(companyId) }
    }, 'Talent Check failed');
    setNotice('Workflow running: generating evidence-grounded AI readiness coaching…');
    const talentData = await runTalentAndCoach(talentProfile, companyId, basicTalentData);
    setTalent(talentData);

    setNotice('Workflow running: matching candidate against the job…');
    const job = {
      job_id: jdData.jd_id || 'uploaded-jd',
      source_file: jdData.source_file,
      company_id: companyIdForMatch(companyId),
      required_skills: jdData.required_skills || jdData.skills?.filter((s) => s.requirement_type === 'required') || [],
      preferred_skills: jdData.preferred_skills || jdData.skills?.filter((s) => s.requirement_type === 'preferred') || []
    };

    const matchData = await call('/api/skill-match', {
      method: 'POST',
      json: {
        profile: { ...saved.profile, candidate_id: saved.profile.candidate_id },
        job,
        jd_id: jdData.jd_id || undefined
      }
    }, 'Skill Matching failed');

    setMatch(matchData);
    setActiveNav('flow-workspace');
    setNotice('Full workflow completed: JD analysed, resume parsed, profile saved, Talent Check calculated, AI readiness coaching attempted, and Skill Matching completed. Review each dashboard for results.');
  });

  const connected = health?.status === 'ok';
  const stagesState = { jd, resumeParsed, profile, talent, match };

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard, group: 'WORKSPACE' },
    { id: 'flow-workspace', label: 'Flow control', icon: Workflow, group: 'WORKSPACE' },
    { id: 'jd-workspace', label: 'JD Analytics', icon: BriefcaseBusiness, number: '01', group: 'ASSESSMENT FLOW' },
    { id: 'resume-workspace', label: 'Resume Parsing', icon: ScanText, number: '02', group: 'ASSESSMENT FLOW' },
    { id: 'profile-workspace', label: 'Profile Builder', icon: UserRound, number: '03', group: 'ASSESSMENT FLOW' },
    { id: 'talent-workspace', label: 'Talent Check', icon: BarChart3, number: '04', group: 'ASSESSMENT FLOW' },
    { id: 'match-workspace', label: 'Skill Matching', icon: GitCompareArrows, number: '05', group: 'ASSESSMENT FLOW' },
    { id: 'evidence-workspace', label: 'Evidence & Eval', icon: ClipboardList, group: 'QUALITY & EVIDENCE' },
    { id: 'about-workspace', label: 'About & Privacy', icon: ShieldCheck, group: 'INFORMATION' }
  ];

  return (
    <div className="radix-app">
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar--open' : ''}`}>
        <button className="sidebar-brand" onClick={() => navigate('overview')} aria-label="RADIX home">
          <span className="brand-symbol">R<span>.</span></span>
          <span className="brand-name"><b>RADIX</b><small>TALENT MATCH</small></span>
          <span className="brand-edition">/ 26</span>
        </button>

        <div className="sidebar-caption">CANDIDATE INTELLIGENCE</div>
        <nav className="side-nav" aria-label="Primary navigation">
          {navItems.map((item, i) => (
            <React.Fragment key={item.id}>
              {item.group && item.group !== navItems[i - 1]?.group && <div className={`nav-group-label ${i ? 'nav-group-label--spaced' : ''}`}>{item.group}</div>}
              <button className={`side-link ${activeNav === item.id ? 'is-active' : ''}`} onClick={() => navigate(item.id)}>
                <span className="side-link__icon"><item.icon size={17} /></span>
                <span className="side-link__label">{item.label}</span>
                {item.number && <span className="side-link__number">{item.number}</span>}
                {activeNav === item.id && <span className="side-link__active" />}
              </button>
            </React.Fragment>
          ))}
        </nav>

        <div className="sidebar-spacer" />
        <div className="sidebar-connection">
          <div className="sidebar-connection__top">
            <span className={`status-led ${connected ? 'is-on' : ''}`} />
            <span>{connected ? 'API CONNECTED' : health?.status === 'offline' ? 'API OFFLINE' : 'CONNECTING'}</span>
            <Activity size={14} />
          </div>
          <p>{connected ? 'Backend responded to health check.' : 'Start FastAPI locally to connect the workspace.'}</p>
          <button onClick={() => { setSettingsOpen(true); setMobileNavOpen(false); }}>
            <Settings2 size={14} /> Connection settings <ArrowRight size={13} />
          </button>
        </div>

        <div className="sidebar-foot">
          <span>RADIX / PLACEMENT INTELLIGENCE</span>
          <span>FIVE MODULE SYSTEM</span>
        </div>
      </aside>

      {mobileNavOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}

      <div className="main-shell">
        <header className="app-topbar">
          <button className="mobile-menu icon-button" onClick={() => setMobileNavOpen((v) => !v)} aria-label="Toggle navigation"><Menu size={20} /></button>
          <div className="breadcrumb">
            <span>RADIX</span><ChevronRight size={13} />
            <b>{activeNav === 'overview' ? 'OVERVIEW' : (navItems.find((n) => n.id === activeNav)?.label || 'ASSESSMENT').toUpperCase()}</b>
          </div>
          <div className="topbar-right">
            <span className={`api-pill ${connected ? 'api-pill--on' : health?.status === 'offline' ? 'api-pill--off' : ''}`}>
              <i />{connected ? 'LIVE API' : health?.status === 'offline' ? 'API OFFLINE' : 'CHECKING API'}
            </span>
            <button className="topbar-icon" onClick={() => setRefreshKey((k) => k + 1)} aria-label="Refresh connection status" title="Refresh connection status"><Activity size={16} /></button>
            <button className="topbar-settings" onClick={() => setSettingsOpen(true)}><Settings2 size={15} /><span>Settings</span></button>
          </div>
        </header>

        <main className="content-area">
          {activeNav === 'overview' && (
            <>
              <section className="dashboard-hero" id="overview-workspace">
                <div className="dashboard-hero__copy">
                  <div className="eyebrow"><span className="eyebrow-line" /> JOB INTELLIGENCE / WORKSPACE 001</div>
                  <h1>Know the gap.<br /><em>Close the gap.</em></h1>
                  <p className="hero-description">A connected candidate assessment workspace. Each module has its own dashboard, consistent typography and focused results.</p>
                  <div className="hero-actions">
                    <button className="btn btn-primary" onClick={() => navigate('jd-workspace')}>Start assessment <ArrowRight size={16} /></button>
                    <span className="hero-aside-note"><ShieldCheck size={15} /> Evidence before estimates</span>
                  </div>
                  <div className="hero-index"><span>01 - 05</span><span>ONE CONNECTED CANDIDATE FLOW</span></div>
                </div>
                <SignalMap />
                <div className="hero-stamp"><span>RADIX</span><span>READINESS IS<br />MORE THAN A NUMBER.</span></div>
              </section>

              <section className="signal-stats" aria-label="Live connection status">
                <MetricSignal icon={Activity} label="API STATUS" value={connected ? 'Connected' : health?.status === 'offline' ? 'Offline' : 'Checking'} detail={connected ? 'FastAPI responded' : health?.error || 'Checking backend health'} tone={connected ? 'green' : 'neutral'} />
                <MetricSignal icon={ScanText} label="AI EXTRACTION" value={integrations?.ai?.configured ? 'Configured' : 'Needs setup'} detail={integrations?.ai?.configured ? (integrations.ai.providers || []).map((p) => p.provider).join(' + ') || 'Provider available' : 'Configure provider key in backend/.env'} tone={integrations?.ai?.configured ? 'green' : 'neutral'} />
                <MetricSignal icon={Database} label="PERSISTENCE" value={integrations?.supabase?.persistence_ready ? 'Supabase ready' : integrations?.supabase?.connected ? 'Tables needed' : health?.storage_mode === 'local-file' ? 'Local files' : 'Checking'} detail={integrations?.supabase?.persistence_ready ? 'Database tables are reachable' : health?.storage_mode === 'local-file' ? 'Saved files remain on backend machine' : 'Check integration status'} tone={integrations?.supabase?.persistence_ready ? 'green' : 'neutral'} />
                <MetricSignal icon={Clock3} label="ASSESSMENT FLOW" value={`${[jd, resumeParsed, profile.skills.length > 0, talent, match].filter(Boolean).length} / 5 stages`} detail="Progress from actual module output" tone="neutral" />
              </section>

              <section className="workflow-section">
                <div className="section-heading">
                  <div>
                    <div className="kicker">ASSESSMENT WORKSPACE</div>
                    <h2>Five modules. Five focused dashboards.</h2>
                    <p>Open a module from the sidebar. Your data carries across dashboards.</p>
                  </div>
                </div>
                <StepRail state={stagesState} onNavigate={navigate} />
              </section>

              <section className="workflow-runner">
                <div>
                  <div className="kicker">AUTOMATED END-TO-END TEST</div>
                  <h2>Run the full candidate workflow</h2>
                  <p>Uses the JD and resume files selected in their dashboards, then analyses, parses, saves the profile, runs Talent Check and Skill Matching in sequence.</p>
                </div>
                <button className="btn btn-primary" onClick={runFullWorkflow} disabled={!!busy || !connected}>
                  {busy === 'workflow' ? <><Activity className="spin" size={16} /> Running workflow…</> : <>Run full workflow <ArrowRight size={16} /></>}
                </button>
                {!connected && <small className="workflow-hint">Connect the backend before running the end-to-end workflow.</small>}
              </section>
            </>
          )}

          {activeNav === 'flow-workspace' && (
            <FlowDashboard
              state={stagesState}
              connected={connected}
              busy={busy}
              jdFile={jdFile}
              resumeFile={resumeFile}
              onNavigate={navigate}
              onRunWorkflow={runFullWorkflow}
            />
          )}

          {activeNav === 'jd-workspace' && (
            <section className="module-screen">
              <div className="screen-heading"><div className="kicker">MODULE 01 / INPUT ANALYSIS</div><h1>JD Analytics</h1><p>Upload a job description and inspect required and preferred skill extraction. The result is passed directly into Skill Matching.</p></div>
              <div className="screen-panel"><JdPanel jd={jd} stats={jdStats} jdFile={jdFile} setJdFile={selectJdFile} busy={busy} onAnalyse={analyseJd} /></div>
              <div className="screen-actions"><button className="btn btn-quiet" onClick={() => navigate('resume-workspace')}>Next: Resume Parsing <ArrowRight size={16} /></button></div>
            </section>
          )}

          {activeNav === 'resume-workspace' && (
            <section className="module-screen">
              <div className="screen-heading"><div className="kicker">MODULE 02 / EVIDENCE EXTRACTION</div><h1>Resume Parsing</h1><p>Extract skills from a candidate resume and merge them into the shared profile. Review the parsed evidence before continuing.</p></div>
              <div className="screen-panel"><ResumePanel resumeFile={resumeFile} setResumeFile={selectResumeFile} busy={busy} onParse={parseResume} parsedResume={resumeResult} /></div>
              <div className="screen-actions"><button className="btn btn-quiet" onClick={() => navigate('profile-workspace')}>Next: Profile Builder <ArrowRight size={16} /></button></div>
            </section>
          )}

          {activeNav === 'profile-workspace' && (
            <section className="module-screen">
              <div className="screen-heading"><div className="kicker">MODULE 03 / CANDIDATE RECORD</div><h1>Profile Builder</h1><p>Review parsed information, correct the candidate details and save the profile before running assessments.</p></div>
              <div className="screen-panel"><ProfilePanel profile={profile} update={update} busy={busy} savedId={savedId} onSave={saveProfile} onLoad={loadProfile} onReview={reviewProfile} review={profileReview} savedCandidates={savedCandidates} onSelectCandidate={selectSavedCandidate} completeness={profileCompleteness} onImport={importProfileData} /></div>
              <div className="screen-actions"><button className="btn btn-quiet" onClick={() => navigate('talent-workspace')}>Next: Talent Check <ArrowRight size={16} /></button></div>
            </section>
          )}

          {activeNav === 'talent-workspace' && (
            <section className="module-screen">
              <div className="screen-heading"><div className="kicker">MODULE 04 / BENCHMARK READINESS</div><h1>Talent Check</h1><p>Compare candidate skills with the selected company benchmark. Unassessed categories are not treated as zero.</p></div>
              <div className="screen-panel"><ResultsPanel mode="talent" companies={companies} companyId={companyId} setCompanyId={changeCompany} busy={busy} onTalent={runTalent} onMatch={runMatch} talent={talent} match={match} jd={jd} /></div>
              <div className="screen-actions"><button className="btn btn-quiet" onClick={() => navigate('match-workspace')}>Next: Skill Matching <ArrowRight size={16} /></button></div>
            </section>
          )}

          {activeNav === 'match-workspace' && (
            <section className="module-screen">
              <div className="screen-heading"><div className="kicker">MODULE 05 / JOB-SPECIFIC FIT</div><h1>Skill Matching</h1><p>Compare the candidate profile with the analysed JD. Review matched skills and prioritized gaps.</p></div>
              <div className="screen-panel"><ResultsPanel mode="match" companies={companies} companyId={companyId} setCompanyId={changeCompany} busy={busy} onTalent={runTalent} onMatch={runMatch} talent={talent} match={match} jd={jd} /></div>
              <div className="screen-actions"><button className="btn btn-quiet" onClick={() => navigate('overview')}>Back to Overview <ArrowRight size={16} /></button></div>
            </section>
          )}

          {activeNav === 'evidence-workspace' && (
            <EvidenceDashboard evaluation={evaluation} savedCandidates={savedCandidates} matrix={readinessMatrix} jdStats={jdStats} jd={jd} loading={evidenceBusy} onRefresh={refreshEvidence} onLoadMatrix={refreshEvidence} />
          )}

          {activeNav === 'about-workspace' && <AboutPrivacyPage />}

          {notice && (
            <div className="notice" role="status">
              <span>{notice}</span>
              <button className="icon-button" onClick={() => setNotice('')} aria-label="Dismiss message"><X size={15} /></button>
            </div>
          )}

          <footer className="app-footer">
            <div className="footer-brand"><span className="brand-symbol brand-symbol--small">R<span>.</span></span><b>RADIX / TALENT MATCH</b></div>
            <p>Scores are estimates, not hiring decisions. Unassessed skills remain unscored.</p>
            <button onClick={() => setSettingsOpen(true)}><CircleHelp size={14} /> API & setup <ArrowRight size={13} /></button>
          </footer>
        </main>
      </div>

      <BackendSettings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        current={apiBase}
        onSave={(value) => {
          setApiBaseState(value);
          setNotice('Backend URL saved. Rechecking API, AI and database status.');
          setRefreshKey((k) => k + 1);
        }}
      />
    </div>
  );
}
