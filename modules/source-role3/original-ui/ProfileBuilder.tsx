import { useState, type ReactNode } from "react";
import {
  Award, Briefcase, Code2, Download, Eye, EyeOff, FileText, GraduationCap, Plus, RotateCcw,
  Save, Sparkles, Target, Trash2, Trophy, UploadCloud, User, type LucideIcon,
} from "lucide-react";
import {
  CATEGORY_CODES,
  CONFIDENCE_LEVELS,
  emptyProfile,
  emptySkill,
  isAcceptedCv,
  validateProfile,
  type CandidateProfile,
  type Skill,
} from "@/lib/profile";
import { loadProfile, saveProfile } from "@/lib/profileStorage";
import { requestResumeParsing } from "@/lib/resumeParsing";

type ListKey = "hackathons" | "internships" | "certifications" | "preferred_roles";

const LISTS: { key: ListKey; label: string; placeholder: string; icon: LucideIcon }[] = [
  { key: "hackathons", label: "Hackathons", placeholder: "e.g. Smart India Hackathon 2025 – finalist", icon: Trophy },
  { key: "internships", label: "Internships", placeholder: "e.g. Backend intern, Acme (3 months)", icon: Briefcase },
  { key: "certifications", label: "Certifications", placeholder: "e.g. AWS Cloud Practitioner", icon: Award },
  { key: "preferred_roles", label: "Preferred Roles", placeholder: "e.g. Software Engineer", icon: Target },
];

const CONFIDENCE_STYLE: Record<Skill["confidence"], string> = {
  high: "bg-primary/15 text-accent-foreground",
  medium: "bg-secondary text-secondary-foreground",
  low: "bg-muted text-muted-foreground",
};

function completion(p: CandidateProfile): number {
  const checks = [
    p.name.trim(), p.email.trim(), p.education.trim(), p.cv_file,
    p.skills.some((s) => s.skill_name.trim()),
    p.hackathons.some((x) => x.trim()), p.internships.some((x) => x.trim()),
    p.certifications.some((x) => x.trim()), p.preferred_roles.some((x) => x.trim()),
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}

export function ProfileBuilder() {
  const [profile, setProfile] = useState<CandidateProfile>(emptyProfile);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<{ name?: string | undefined; email?: string | undefined }>({});
  const [message, setMessage] = useState<{ text: string; tone: "ok" | "warn" } | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [dragging, setDragging] = useState(false);

  const set = <K extends keyof CandidateProfile>(k: K, v: CandidateProfile[K]) =>
    setProfile((p) => ({ ...p, [k]: v }));
  const notify = (text: string, tone: "ok" | "warn" = "ok") => setMessage({ text, tone });

  const updateSkill = (i: number, patch: Partial<Skill>) =>
    set("skills", profile.skills.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  const updateItem = (k: ListKey, i: number, v: string) =>
    set(k, profile[k].map((x, idx) => (idx === i ? v : x)));

  const onCvChange = (file: File | undefined) => {
    if (!file) return;
    if (!isAcceptedCv(file.name)) {
      notify("Please choose a PDF or DOCX file.", "warn");
      return;
    }
    setCvFile(file);
    set("cv_file", file.name);
    setMessage(null);
  };

  const onParse = async () => {
    if (!cvFile) return notify("Choose a CV file first.", "warn");
    const r = await requestResumeParsing(cvFile);
    if (!r.ok) return notify(r.message, "warn");
    setProfile((p) => ({ ...p, ...r.profile }));
    notify("Resume parsed.");
  };

  const onSave = async () => {
    const e = validateProfile(profile);
    setErrors(e);
    if (Object.keys(e).length) return notify("Fix the highlighted fields before saving.", "warn");
    await saveProfile(profile);
    notify("Profile saved.");
  };

  const onLoad = async () => {
    const p = await loadProfile();
    if (!p) return notify("No saved profile found.", "warn");
    setProfile(p);
    setCvFile(null);
    setErrors({});
    notify(p.cv_file ? `Profile loaded. Re-select the CV file to upload it (${p.cv_file}).` : "Profile loaded.");
  };

  const onClear = () => {
    setProfile(emptyProfile());
    setCvFile(null);
    setErrors({});
    setShowJson(false);
    notify("Form cleared.");
  };

  const pct = completion(profile);

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-hero text-navy-foreground">
        <div className="mx-auto flex max-w-5xl flex-col gap-5 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="h-5 w-5" aria-hidden />
            </div>
            <div>
              <h1 className="text-lg font-extrabold tracking-tight sm:text-xl">RADIX Talent Match</h1>
              <p className="text-sm opacity-80">Build your profile. Discover your potential.</p>
            </div>
          </div>
          <div className="w-full sm:w-64" aria-label={`Profile ${pct}% complete`}>
            <div className="mb-1.5 flex justify-between text-xs font-semibold">
              <span className="opacity-80">Profile completion</span>
              <span>{pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-navy-foreground/15" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-progress transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-5 px-4 py-8 sm:px-6 lg:grid-cols-2">
        <Card title="Personal Information" icon={User}>
          <Field label="Name" required error={errors.name}>
            <input className="field-input" value={profile.name} maxLength={100} placeholder="Your full name" onChange={(e) => set("name", e.target.value)} aria-invalid={!!errors.name} />
          </Field>
          <Field label="Email" required error={errors.email}>
            <input className="field-input" type="email" value={profile.email} maxLength={255} placeholder="you@example.com" onChange={(e) => set("email", e.target.value)} aria-invalid={!!errors.email} />
          </Field>
          <Field label="Education">
            <div className="relative">
              <GraduationCap className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <input className="field-input pl-9" value={profile.education} placeholder="e.g. B.Tech CSE, 2026" onChange={(e) => set("education", e.target.value)} />
            </div>
          </Field>
        </Card>

        <Card title="CV Upload" icon={FileText}>
          <label
            className={
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors " +
              (dragging ? "border-primary bg-accent" : "border-input hover:border-primary hover:bg-accent/50")
            }
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); onCvChange(e.dataTransfer.files?.[0]); }}
          >
            <UploadCloud className="h-8 w-8 text-primary" aria-hidden />
            <span className="text-sm font-semibold">Drop your CV here or <span className="text-primary underline underline-offset-2">browse</span></span>
            <span className="text-xs text-muted-foreground">PDF or DOCX</span>
            <input
              type="file"
              className="sr-only"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => { onCvChange(e.target.files?.[0]); e.target.value = ""; }}
            />
          </label>
          {profile.cv_file ? (
            <div className="flex items-center gap-2 rounded-md bg-secondary px-3 py-2 text-sm">
              <FileText className="h-4 w-4 shrink-0 text-primary" aria-hidden />
              <span className="truncate font-medium">{profile.cv_file}</span>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No file selected.</p>
          )}
          <button type="button" className="btn w-full justify-center" onClick={onParse}>
            <Sparkles className="h-4 w-4" aria-hidden /> Parse resume
          </button>
        </Card>

        <Card
          title="Skills"
          icon={Code2}
          count={profile.skills.length}
          className="lg:col-span-2"
          action={<AddButton label="Add skill" onClick={() => set("skills", [...profile.skills, emptySkill()])} />}
        >
          {profile.skills.length === 0 && <Empty text="Add skills with evidence to strengthen your profile." />}
          <div className="grid gap-3">
            {profile.skills.map((s, i) => (
              <div key={i} className="rounded-lg border border-border bg-background/60 p-3 sm:p-4">
                <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end">
                  <Field label="Skill name">
                    <input className="field-input" placeholder="e.g. React" value={s.skill_name} onChange={(e) => updateSkill(i, { skill_name: e.target.value })} />
                  </Field>
                  <Field label="Category">
                    <select className="field-input" value={s.category_code} onChange={(e) => updateSkill(i, { category_code: e.target.value as Skill["category_code"] })}>
                      {CATEGORY_CODES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </Field>
                  <Field label="Confidence">
                    <select className={"field-input font-semibold capitalize " + CONFIDENCE_STYLE[s.confidence]} value={s.confidence} onChange={(e) => updateSkill(i, { confidence: e.target.value as Skill["confidence"] })}>
                      {CONFIDENCE_LEVELS.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </Field>
                  <button type="button" className="btn-ghost-danger justify-self-end" aria-label={`Remove skill ${i + 1}`} onClick={() => set("skills", profile.skills.filter((_, idx) => idx !== i))}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <div className="mt-3">
                  <Field label="Evidence">
                    <input className="field-input" placeholder="Project, link, course, or achievement" value={s.evidence} onChange={(e) => updateSkill(i, { evidence: e.target.value })} />
                  </Field>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {LISTS.map(({ key, label, placeholder, icon }) => (
          <Card key={key} title={label} icon={icon} count={profile[key].length} action={<AddButton label="Add" onClick={() => set(key, [...profile[key], ""])} />}>
            {profile[key].length === 0 && <Empty text="None added yet." />}
            {profile[key].map((v, i) => (
              <div key={i} className="flex gap-2">
                <input className="field-input" placeholder={placeholder} value={v} aria-label={`${label} ${i + 1}`} onChange={(e) => updateItem(key, i, e.target.value)} />
                <button type="button" className="btn-ghost-danger" aria-label={`Remove ${label} ${i + 1}`} onClick={() => set(key, profile[key].filter((_, idx) => idx !== i))}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </Card>
        ))}

        <div className="space-y-4 lg:col-span-2">
          {message && (
            <p role="status" className={"rounded-lg px-4 py-3 text-sm font-medium " + (message.tone === "ok" ? "bg-accent text-accent-foreground" : "bg-destructive/10 text-destructive")}>
              {message.text}
            </p>
          )}
          <div className="flex flex-wrap gap-2 rounded-xl border border-border bg-card p-3 shadow-card">
            <button type="button" className="btn btn-primary" onClick={onSave}><Save className="h-4 w-4" aria-hidden /> Save Profile</button>
            <button type="button" className="btn" onClick={onLoad}><Download className="h-4 w-4" aria-hidden /> Load Profile</button>
            <button type="button" className="btn" onClick={onClear}><RotateCcw className="h-4 w-4" aria-hidden /> Clear Form</button>
            <button type="button" className="btn btn-navy sm:ml-auto" onClick={() => setShowJson((v) => !v)}>
              {showJson ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
              {showJson ? "Hide JSON" : "Preview JSON"}
            </button>
          </div>
          {showJson && (
            <pre className="max-h-[480px] overflow-auto rounded-xl bg-navy p-5 text-xs leading-relaxed text-navy-foreground shadow-card">
              {JSON.stringify(profile, null, 2)}
            </pre>
          )}
        </div>
      </main>
    </div>
  );
}

function Card({ title, icon: Icon, count, action, className = "", children }: {
  title: string; icon: LucideIcon; count?: number | undefined; action?: ReactNode | undefined; className?: string | undefined; children: ReactNode;
}) {
  return (
    <section className={"space-y-4 rounded-xl border border-border bg-card p-5 shadow-card " + className}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <Icon className="h-4 w-4" aria-hidden />
          </span>
          <h2 className="font-bold text-card-foreground">{title}</h2>
          {count !== undefined && count > 0 && (
            <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-semibold text-secondary-foreground">{count}</span>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" className="btn px-2.5 py-1.5 text-xs" onClick={onClick}>
      <Plus className="h-3.5 w-3.5" aria-hidden /> {label}
    </button>
  );
}

function Field({ label, required, error, children }: { label: string; required?: boolean | undefined; error?: string | undefined; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}{required && <span className="text-destructive"> *</span>}
      </span>
      {children}
      {error && <span className="block text-xs font-medium text-destructive">{error}</span>}
    </label>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-lg bg-muted px-3 py-3 text-sm text-muted-foreground">{text}</p>;
}
