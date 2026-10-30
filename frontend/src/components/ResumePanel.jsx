import React from 'react';
import {
  AlertTriangle, CheckCircle2, FileUser, GitCompareArrows, LoaderCircle,
  ShieldCheck, Upload
} from 'lucide-react';

function SkillCard({ skill, label }) {
  return (
    <article className="resume-compare__skill">
      <div className="resume-compare__skill-head">
        <b>{skill.skill_name}</b>
        <span>{label}</span>
      </div>
      {skill.evidence && <p>{skill.evidence}</p>}
      <small>{skill.category_code || 'Uncategorised'} · {skill.confidence || 'confidence not supplied'}</small>
    </article>
  );
}

export default function ResumePanel({
  resumeFile, setResumeFile, busy, onParse, parsedResume,
  comparison, providerCount = 0, onCompare
}) {
  const summary = comparison?.summary;
  const canCompare = parsedResume?.extraction_method === 'llm'
    && Boolean(parsedResume?.ai_metadata?.model_used)
    && providerCount >= 2;
  const comparisonBusy = busy === 'resume-comparison';

  return (
    <section className="panel">
      <div className="panelhead">
        <div className="iconbox violet"><FileUser /></div>
        <div>
          <div className="kicker">ROLE 2</div>
          <h2>Resume Parsing</h2>
          <p>Extract candidate information, then optionally check whether another AI provider finds the same skills.</p>
        </div>
      </div>

      <label className="drop">
        <Upload />
        <b>{resumeFile?.name || 'Choose a candidate resume'}</b>
        <small>PDF or DOCX · max 8 MB</small>
        <input type="file" accept=".pdf,.docx" onChange={e => setResumeFile(e.target.files?.[0] || null)} />
      </label>

      <button className="btn primary" onClick={onParse} disabled={!!busy}>
        {busy === 'resume' ? <LoaderCircle className="spin" /> : <FileUser size={16} />}
        Parse resume
      </button>
      <p className="micro">Parser output is a draft. It never invents a skill level; you set levels below. Review before using the scores.</p>

      {parsedResume && (
        <section className="resume-parse-result" aria-live="polite">
          <div className="resume-parse-result__head">
            <div>
              <div className="kicker">PRIMARY EXTRACTION</div>
              <h3>Resume parsed</h3>
              <p>{parsedResume.ai_metadata?.model_used || 'Keyword fallback'} · {parsedResume.profile?.skills?.length || 0} grounded skills returned</p>
            </div>
            <span className={parsedResume.extraction_method === 'llm' ? 'resume-status resume-status--ai' : 'resume-status'}>
              {parsedResume.extraction_method === 'llm' ? 'AI EXTRACTION' : 'KEYWORD FALLBACK'}
            </span>
          </div>

          <div className="resume-compare">
            <div className="resume-compare__intro">
              <div className="resume-compare__intro-icon"><GitCompareArrows size={18} /></div>
              <div>
                <div className="kicker">OPTIONAL / INDEPENDENT CHECK</div>
                <h3>Cross-model agreement</h3>
                <p>Ask a different configured provider to extract skills from the same resume. RADIX compares the two grounded skill lists without changing your profile.</p>
              </div>
            </div>

            <div className="resume-privacy-note">
              <ShieldCheck size={16} />
              <span>This sends the resume text to one additional AI provider only after you click. It uses another model call, may incur provider usage, and the comparison is not saved or merged into the candidate profile.</span>
            </div>

            <div className="resume-compare__action">
              <button className="btn btn-quiet" onClick={onCompare} disabled={!!busy || !canCompare}>
                {comparisonBusy ? <LoaderCircle className="spin" size={15} /> : <GitCompareArrows size={15} />}
                {comparisonBusy ? 'Comparing providers…' : 'Compare with another provider'}
              </button>
              {!canCompare && (
                <small>
                  {parsedResume.extraction_method !== 'llm' || !parsedResume.ai_metadata?.model_used
                    ? 'Run a successful AI extraction first. Keyword fallback cannot be independently compared.'
                    : 'Configure at least two different AI providers in the backend to enable this check.'}
                </small>
              )}
            </div>
          </div>
        </section>
      )}

      {comparison && summary && (
        <section className="resume-compare__results" aria-live="polite">
          <div className="resume-compare__results-head">
            <div>
              <div className="kicker">CROSS-PROVIDER RESULT</div>
              <h3>Extraction overlap</h3>
              <p>{comparison.primary_model} <span>vs</span> {comparison.verifier_model}</p>
            </div>
            <span className="resume-status resume-status--ai">COMPLETE</span>
          </div>

          <div className="resume-compare__metrics">
            <div><small>Shared skills</small><strong>{summary.agreed}</strong></div>
            <div><small>Primary only</small><strong>{summary.primary_only}</strong></div>
            <div><small>Second provider only</small><strong>{summary.verifier_only}</strong></div>
            <div><small>Skill overlap</small><strong>{summary.skill_overlap_pct}%</strong></div>
          </div>

          <div className="resume-compare__bar" aria-label={summary.skill_overlap_pct + '% skill overlap'}>
            <i style={{ width: summary.skill_overlap_pct + '%' }} />
          </div>
          <p className="resume-compare__bar-note">Overlap = skills both providers found ÷ distinct skills found by either provider.</p>

          <div className="resume-compare__section">
            <h4><CheckCircle2 size={15} /> Both providers found ({summary.agreed})</h4>
            {comparison.agreed?.length ? comparison.agreed.map((item, index) => (
              <article className="resume-compare__agreement" key={item.skill_name + index}>
                <b>{item.skill_name}</b>
                <div className="resume-compare__evidence-grid">
                  <div><small>{comparison.primary_model}</small><p>{item.primary_evidence}</p></div>
                  <div><small>{comparison.verifier_model}</small><p>{item.verifier_evidence}</p></div>
                </div>
              </article>
            )) : <p className="resume-compare__empty">No shared skills were found in this run.</p>}
          </div>

          <div className="resume-compare__differences">
            <div className="resume-compare__section">
              <h4><AlertTriangle size={15} /> Primary only ({summary.primary_only})</h4>
              {comparison.primary_only?.length ? comparison.primary_only.map((skill, index) => (
                <SkillCard key={skill.skill_name + index} skill={skill} label="Not returned by verifier" />
              )) : <p className="resume-compare__empty">No primary-only skills.</p>}
            </div>
            <div className="resume-compare__section">
              <h4><AlertTriangle size={15} /> Second provider only ({summary.verifier_only})</h4>
              {comparison.verifier_only?.length ? comparison.verifier_only.map((skill, index) => (
                <SkillCard key={skill.skill_name + index} skill={skill} label="Not returned by primary" />
              )) : <p className="resume-compare__empty">No verifier-only skills.</p>}
            </div>
          </div>

          <div className="resume-compare__disclaimer">{comparison.disclaimer}</div>
        </section>
      )}
    </section>
  );
}
