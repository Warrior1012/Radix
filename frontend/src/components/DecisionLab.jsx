import React, { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowRight, CheckCircle2, FlaskConical, ShieldCheck, Sparkles } from 'lucide-react';
import { call } from '../api.js';
import './DecisionLab.css';

const STATUS = {
  level_entered: { label: 'Level entered', tone: 'level' },
  evidence_available: { label: 'Evidence available', tone: 'evidence' },
  claimed: { label: 'Claimed', tone: 'claim' },
  unassessed: { label: 'Unassessed', tone: 'unknown' },
};

function safeProfile(profile) {
  return {
    ...profile,
    skills: (Array.isArray(profile?.skills) ? profile.skills : [])
      .filter((skill) => skill && String(skill.skill_name || '').trim()),
  };
}

function safeJob(jd) {
  const skills = Array.isArray(jd?.skills) ? jd.skills : [];
  return {
    job_id: jd?.jd_id || jd?.job_id || 'request-job',
    source_file: jd?.source_file || jd?.jd_source_file || '',
    company: jd?.company || jd?.company_name || '',
    role: jd?.role || jd?.job_title || '',
    required_skills: Array.isArray(jd?.required_skills)
      ? jd.required_skills
      : skills.filter((skill) => (skill?.requirement_type || 'required') === 'required').map((skill) => skill.skill_name).filter(Boolean),
    preferred_skills: Array.isArray(jd?.preferred_skills)
      ? jd.preferred_skills
      : skills.filter((skill) => skill?.requirement_type === 'preferred').map((skill) => skill.skill_name).filter(Boolean),
    skills,
  };
}

function StatusTag({ status }) {
  const item = STATUS[status] || STATUS.unassessed;
  return <span className={`decision-status decision-status--${item.tone}`}>{item.label}</span>;
}

function Metric({ label, value, hint }) {
  return <div className="decision-metric">
    <span>{label}</span>
    <strong>{value}</strong>
    {hint && <small>{hint}</small>}
  </div>;
}

export default function DecisionLab({ profile, jd }) {
  const [proof, setProof] = useState(null);
  const [selected, setSelected] = useState([]);
  const [simulation, setSimulation] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const readyProfile = useMemo(() => safeProfile(profile), [profile]);
  const readyJob = useMemo(() => safeJob(jd), [jd]);
  const hasJob = Boolean(readyJob.required_skills.length || readyJob.preferred_skills.length);
  const hasSkills = readyProfile.skills.length > 0;

  useEffect(() => {
    setProof(null);
    setSelected([]);
    setSimulation(null);
    setError('');
  }, [profile, jd]);

  async function loadProofGraph() {
    setBusy('proof');
    setError('');
    setSimulation(null);
    try {
      const result = await call('/api/decision-lab/proofgraph', {
        method: 'POST',
        json: { profile: readyProfile, job: readyJob },
      }, 'Could not build ProofGraph');
      setProof(result);
      setSelected([]);
    } catch (e) {
      setError(e?.message || 'Could not build ProofGraph. Check the API connection and profile/JD data.');
    } finally {
      setBusy('');
    }
  }

  async function runSimulation() {
    if (!selected.length) {
      setError('Select at least one unassessed job requirement to simulate.');
      return;
    }
    setBusy('simulation');
    setError('');
    try {
      const result = await call('/api/decision-lab/simulate', {
        method: 'POST',
        json: { profile: readyProfile, job: readyJob, assumed_skills: selected },
      }, 'Could not calculate the hypothetical scenario');
      setSimulation(result);
    } catch (e) {
      setError(e?.message || 'Could not calculate the scenario.');
    } finally {
      setBusy('');
    }
  }

  const requirements = proof?.requirements || [];
  const missingRows = requirements.filter((item) => item.status === 'unassessed');
  const statusCounts = proof?.summary?.status_counts || {};
  const selectedLabel = selected.length === 1 ? 'requirement' : 'requirements';

  function toggleSkill(skill, checked) {
    setSelected((current) => checked
      ? [...current, skill].filter((name, index, all) => all.indexOf(name) === index)
      : current.filter((name) => name !== skill));
    setSimulation(null);
  }

  return <section className="decision-lab">
    <div className="decision-lab__intro">
      <div>
        <div className="kicker">EXPLAINABILITY / HYPOTHETICAL SCENARIOS</div>
        <h2>Decision Lab <span> / ProofGraph</span></h2>
        <p>See which job requirements are supported by profile evidence, which only appear as claims, and which remain unknown. Then model a hypothetical demonstration without changing the saved profile.</p>
      </div>
      <div className="decision-lab__mark"><ShieldCheck size={27}/><span>TRACEABLE<br/>SIGNALS</span></div>
    </div>

    <div className="decision-lab__context">
      <div><span>JOB DESCRIPTION</span><strong>{readyJob.role || 'Selected job'}</strong><small>{readyJob.company || readyJob.source_file || 'Current JD analysis'}</small></div>
      <div><span>CANDIDATE PROFILE</span><strong>{readyProfile.name || 'Current profile'}</strong><small>{readyProfile.skills.length} named skill{readyProfile.skills.length === 1 ? '' : 's'} in the current profile</small></div>
    </div>

    {(!hasJob || !hasSkills) && <div className="decision-empty">
      <strong>{!hasJob ? 'Analyse a JD first.' : 'Add candidate skills first.'}</strong>
      <p>{!hasJob ? 'Open JD Analytics and analyse a job description with required or preferred skills.' : 'Parse a resume or add at least one skill in Profile Builder, then return here.'}</p>
    </div>}

    <div className="decision-lab__actions">
      <button className="btn btn-primary" onClick={loadProofGraph} disabled={!hasJob || !hasSkills || Boolean(busy)}>
        {busy === 'proof' ? <><Activity size={15} className="spin"/> Building evidence map…</> : <><ShieldCheck size={15}/> Build ProofGraph</>}
      </button>
      {proof && <span className="decision-lab__note">Read-only · no profile changes</span>}
    </div>

    {error && <div className="decision-error" role="alert">{error}</div>}

    {proof && <>
      <div className="decision-metrics">
        <Metric label="JD requirements" value={proof.summary?.requirements ?? 0} hint={`${proof.summary?.required ?? 0} required · ${proof.summary?.preferred ?? 0} preferred`}/>
        <Metric label="Level entered" value={statusCounts.level_entered ?? 0} hint="Explicit 1–10 level"/>
        <Metric label="Evidence available" value={statusCounts.evidence_available ?? 0} hint="Evidence text, no level"/>
        <Metric label="Unassessed gaps" value={statusCounts.unassessed ?? 0} hint="No matched profile skill"/>
      </div>

      <div className="decision-section-head">
        <div><span className="kicker">01 / REQUIREMENT TRACE</span><h3>What supports the match?</h3></div>
        <span>{requirements.length} requirements mapped</span>
      </div>

      <div className="decision-requirements">
        {requirements.map((item) => <article className="decision-requirement" key={`${item.requirement_type}-${item.skill}`}>
          <div className="decision-requirement__main">
            <div className="decision-requirement__title">
              <strong>{item.skill}</strong>
              <span className="decision-requirement__type">{item.requirement_type === 'required' ? 'REQUIRED' : 'PREFERRED'}</span>
            </div>
            <StatusTag status={item.status}/>
            {item.matched_with && <small className="decision-requirement__match">Matched to profile skill: {item.matched_with}{item.candidate_level != null ? ` · level ${item.candidate_level}/10` : ''}</small>}
            {item.evidence && <p className="decision-evidence">“{item.evidence}”</p>}
            {!item.matched && <small className="decision-requirement__match">No matching skill found in the current profile. This is unknown, not proof that the candidate lacks the ability.</small>}
            {item.status === 'claimed' && <small className="decision-requirement__match">The skill is listed, but no evidence text or explicit level is available.</small>}
            {item.status === 'evidence_available' && <small className="decision-requirement__match">Evidence is present, but proficiency has not been entered.</small>}
            {item.status === 'level_entered' && <small className="decision-requirement__match">The level is explicitly entered; this does not mean it was independently verified.</small>}
          </div>
          <div className="decision-requirement__points"><span>POINTS AT RISK</span><b>{item.points_lost ?? 0}</b></div>
        </article>)}
      </div>

      <div className="decision-section-head decision-section-head--scenario">
        <div><span className="kicker">02 / WHAT-IF SIMULATOR</span><h3>What if a gap were demonstrated?</h3><p>Select missing requirements to calculate a hypothetical match. Nothing is added to the actual profile.</p></div>
        <FlaskConical size={24}/>
      </div>

      {missingRows.length ? <div className="decision-scenario">
        <div className="decision-scenario__choices">
          {missingRows.map((item) => <label className="decision-choice" key={item.skill}>
            <input type="checkbox" checked={selected.includes(item.skill)} onChange={(event) => toggleSkill(item.skill, event.target.checked)} disabled={Boolean(busy)}/>
            <span><strong>{item.skill}</strong><small>{item.requirement_type === 'required' ? 'Required gap' : 'Preferred gap'} · hypothetical only</small></span>
            <ArrowRight size={14}/>
          </label>)}
        </div>
        <div className="decision-scenario__run">
          <span>{selected.length} {selectedLabel} selected</span>
          <button className="btn btn-primary" onClick={runSimulation} disabled={!selected.length || Boolean(busy)}>
            {busy === 'simulation' ? <><Activity size={15} className="spin"/> Calculating…</> : <><Sparkles size={15}/> Simulate scenario</>}
          </button>
        </div>
      </div> : <div className="decision-empty"><strong>No unmatched JD requirements in this deterministic view.</strong><p>There is no missing requirement to simulate for this job and profile.</p></div>}

      {simulation && <div className="decision-simulation" aria-live="polite">
        <div className="decision-simulation__head"><div><span className="kicker">HYPOTHETICAL RESULT</span><h3>Potential coverage change</h3></div><span className="decision-simulation__flag">NOT SAVED</span></div>
        <div className="decision-simulation__scores">
          <div><span>Current deterministic match</span><strong>{simulation.baseline_score == null ? '—' : `${simulation.baseline_score}%`}</strong></div>
          <div className="decision-simulation__arrow"><ArrowRight size={17}/></div>
          <div><span>Hypothetical match</span><strong>{simulation.scenario_score == null ? '—' : `${simulation.scenario_score}%`}</strong></div>
          <div className="decision-simulation__delta"><span>Change</span><strong>{simulation.score_delta == null ? '—' : `${simulation.score_delta > 0 ? '+' : ''}${simulation.score_delta} pts`}</strong></div>
        </div>
        <p>{simulation.assumption_note}</p>
        <small>Reproducible weighting: required skills count 2 points; preferred skills count 1. This is a scenario, not an assessment result or a hiring recommendation.</small>
      </div>}

      <div className="decision-lab__method"><ShieldCheck size={15}/><span>{proof.methodology}</span></div>
    </>}
  </section>;
}
