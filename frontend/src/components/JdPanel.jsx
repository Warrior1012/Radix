import React from 'react';
import { FileText, Upload, CheckCircle2, LoaderCircle } from 'lucide-react';

function SkillReviewRow({s}) {
  return <div className="jdrow">
    <b>{s.skill_name}</b>
    <span className="tag">{s.category_code}</span>
    <span className={`tag conf-${s.confidence}`}>{s.confidence}</span>
    {s.requirement_basis && <span className="tag faint" title="How required/preferred was decided">{s.requirement_basis.replace(/_/g, ' ')}</span>}
    <q>{s.evidence}</q>
  </div>;
}

export default function JdPanel({jd, stats, jdFile, setJdFile, busy, onAnalyse}) {
  const skills = jd?.skills || [];
  const req = skills.filter(s => s.requirement_type === 'required');
  const pref = skills.filter(s => s.requirement_type === 'preferred');
  const meta = jd?.analysis_meta;
  return <section className="panel">
    <div className="panelhead"><div className="iconbox blue"><FileText/></div><div><div className="kicker">ROLE 1</div><h2>Job Description Analytics</h2><p>Extract required and preferred skills from a PDF or DOCX.</p></div></div>
    <label className="drop"><Upload/><b>{jdFile?.name || 'Choose a job description'}</b><small>PDF or DOCX · max 8 MB</small><input type="file" accept=".pdf,.docx" onChange={e => setJdFile(e.target.files?.[0] || null)}/></label>
    <button className="btn primary" onClick={onAnalyse} disabled={!!busy}>{busy === 'jd' ? <LoaderCircle className="spin"/> : <FileText size={16}/>} Analyse job description</button>
    {jd && <div className="resultmini">
      <div className="resulttitle"><CheckCircle2 size={16}/> {jd.role || 'Job role extracted'} <span>{jd.company || 'Company not detected'}</span></div>
      <small>{req.length} required · {pref.length} preferred · {jd.extraction_method}{meta?.processing_path ? ` · path: ${meta.processing_path}` : ''}</small>
      <small className="handoff">Saved as JD <code>{String(jd.jd_id).slice(0, 8)}</code> - Skill Matching will use this exact analysis.</small>
      {jd.jd_store_warning && <small className="warn">{jd.jd_store_warning}</small>}
      {stats && <section className="jd-insights" aria-label="Measured job description statistics">
        <div className="jd-insights__title"><div><b>Skill distribution</b><small>Counts from this extracted JD</small></div><span>{stats.model_calls ?? 0} model call(s) · {stats.runtime_ms == null ? 'latency n/a' : `${stats.runtime_ms} ms`}</span></div>
        <div className="jd-insights__split"><span>Required <b>{stats.required}</b></span><span>Preferred <b>{stats.preferred}</b></span><span>High confidence <b>{stats.confidence_counts?.high ?? 0}</b></span></div>
        {Object.entries(stats.category_counts || {}).sort((a,b) => b[1]-a[1]).length ? <div className="jd-insights__bars">{Object.entries(stats.category_counts || {}).sort((a,b) => b[1]-a[1]).map(([code,count]) => {
          const max = Math.max(1, ...Object.values(stats.category_counts || {}).map(Number));
          return <div className="jd-insights__row" key={code}><span>{code}</span><div><i style={{width: `${Math.max(4, Number(count) / max * 100)}%`}} /></div><b>{count}</b></div>;
        })}</div> : <small>No skill category counts were returned.</small>}
      </section>}
      <details open><summary>Required ({req.length})</summary>{req.length ? req.map((s, i) => <SkillReviewRow key={'r' + i} s={s}/>) : <small>None found.</small>}</details>
      <details><summary>Preferred ({pref.length})</summary>{pref.length ? pref.map((s, i) => <SkillReviewRow key={'p' + i} s={s}/>) : <small>None found. If the document has a “preferred / nice to have” section this may be an extraction miss.</small>}</details>
    </div>}
  </section>;
}
