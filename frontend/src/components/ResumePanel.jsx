import React from 'react';
import { FileUser, Upload, LoaderCircle } from 'lucide-react';
export default function ResumePanel({resumeFile, setResumeFile, busy, onParse}) {
  return <section className="panel">
    <div className="panelhead"><div className="iconbox violet"><FileUser/></div><div><div className="kicker">ROLE 2</div><h2>Resume Parsing</h2><p>Extract skills, education, projects and experience for profile pre-fill.</p></div></div>
    <label className="drop"><Upload/><b>{resumeFile?.name || 'Choose a candidate resume'}</b><small>PDF or DOCX · max 8 MB</small><input type="file" accept=".pdf,.docx" onChange={e => setResumeFile(e.target.files?.[0] || null)}/></label>
    <button className="btn primary" onClick={onParse} disabled={!!busy}>{busy === 'resume' ? <LoaderCircle className="spin"/> : <FileUser size={16}/>} Parse resume</button>
    <p className="micro">Parser output is a draft. It never invents a skill level - you set levels below. Review before using the scores.</p>
  </section>;
}
