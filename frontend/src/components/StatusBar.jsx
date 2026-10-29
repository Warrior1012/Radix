import React from 'react';
export default function StatusBar({health, integrations}) {
  const ai = integrations?.ai, sb = integrations?.supabase;
  const aiText = ai?.configured ? ai.providers.map(p => p.provider === 'gemini' ? 'Gemini' : p.provider).join(' + ') + ' ready' : 'AI key missing';
  const sbText = sb?.persistence_ready ? 'Supabase connected' : sb?.connected ? 'Supabase needs RADIX tables' : sb?.configured ? 'Supabase connection issue' : 'Supabase not configured';
  return <div className="status"><span className={`dot ${health?.status === 'ok' ? '' : 'bad'}`}></span>{health?.status === 'ok' ? 'API connected' : 'API offline'} <span className="divider">·</span> {aiText} <span className="divider">·</span> {sbText}</div>;
}
