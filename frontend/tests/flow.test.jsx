// End-to-end UI flow against a REAL running backend (set RADIX_TEST_API, e.g. http://127.0.0.1:8765).
// Skipped automatically when RADIX_TEST_API is not set, so `npm test` never fails just because no server is up.
import React from 'react';
import { readFileSync } from 'node:fs';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import App from '../src/App.jsx';

const live = !!process.env.RADIX_TEST_API;
const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const file = (name) => new File([readFileSync(new URL('./fixtures/' + name, import.meta.url))], name, {type: DOCX});
const pick = (label, f) => fireEvent.change(label.querySelector('input[type=file]'), {target: {files: [f]}});

describe.skipIf(!live)('UI flow vs live backend', () => {
  it('JD -> resume -> profile -> talent check -> skill match, with honest unassessed handling', async () => {
    // Test-env shim only: jsdom's FormData/File are not Node's, so hand-build the multipart body (real browsers don't need this).
    const nodeFetch = globalThis.fetch;
    const readBlob = (b) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = () => rej(r.error); r.readAsArrayBuffer(b); });
    const multipart = async (fd) => {
      const boundary = '----radixtest' + Math.random().toString(16).slice(2);
      const parts = [];
      for (const [k, v] of fd.entries()) {
        if (typeof v === 'string') parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="${k}"\r\n\r\n${v}\r\n`));
        else parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="${k}"; filename="${v.name}"\r\nContent-Type: ${v.type || 'application/octet-stream'}\r\n\r\n`), Buffer.from(await readBlob(v)), Buffer.from('\r\n'));
      }
      parts.push(Buffer.from(`--${boundary}--\r\n`));
      return {body: Buffer.concat(parts), type: `multipart/form-data; boundary=${boundary}`};
    };
    window.fetch = globalThis.fetch = async (u, o = {}) => {
      const url = String(u).replace('http://127.0.0.1:8000', process.env.RADIX_TEST_API);
      if (o.body && typeof o.body.entries === 'function' && typeof o.body.append === 'function') {
        const m = await multipart(o.body);
        return nodeFetch(url, {...o, body: m.body, headers: {...(o.headers || {}), 'Content-Type': m.type}});
      }
      return nodeFetch(url, o);
    };
    render(<App/>);
    await waitFor(() => expect(screen.getByText(/API connected/)).toBeTruthy());

    pick(screen.getByText('Choose a job description').closest('label'), file('synthetic_jd.docx'));
    fireEvent.click(screen.getByText('Analyse job description'));
    await waitFor(() => expect(document.querySelector('.notice, .handoff')?.textContent || 'NO-NOTICE').toMatch(/Job description analysed|exact analysis/));

    pick(screen.getByText('Choose a candidate resume').closest('label'), file('synthetic_resume.docx'));
    fireEvent.click(screen.getByText('Parse resume'));
    await waitFor(() => expect(screen.getByText(/Resume parsed using/)).toBeTruthy());

    // Parsed skills arrive WITHOUT a level -> shown as not assessed, never as 0.
    const levelInputs = () => [...document.querySelectorAll('.skillrow .level input')];
    await waitFor(() => expect(levelInputs().length).toBeGreaterThan(0));
    expect(levelInputs().every(i => i.value === '')).toBe(true);
    expect(screen.getAllByText(/Not assessed — left out of Talent Check/).length).toBeGreaterThan(0);

    // Talent Check with nothing assessed: no fake number.
    fireEvent.click(screen.getByText('Run Talent Check'));
    await waitFor(() => expect(screen.getByText(/COMPANY READINESS/)).toBeTruthy());
    expect(document.querySelector('.scorecard .score').textContent.startsWith('—')).toBe(true);

    // Give the first skill a level -> a real score appears.
    fireEvent.change(levelInputs()[0], {target: {value: '7'}});
    fireEvent.click(screen.getByText('Run Talent Check'));
    await waitFor(() => expect(document.querySelector('.scorecard .score').textContent.startsWith('—')).toBe(false));
    expect(document.querySelectorAll('.catrow').length).toBe(12);

    fireEvent.click(screen.getByText('Run Skill Matching'));
    await waitFor(() => expect(screen.getByText(/JOB-SPECIFIC MATCH/)).toBeTruthy());
    expect(screen.getByText(/saved analysis/)).toBeTruthy();
    expect(screen.getByText(/Missing skills/)).toBeTruthy();
    cleanup();
  });
});
