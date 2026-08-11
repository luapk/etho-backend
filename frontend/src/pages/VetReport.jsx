import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Printer, Copy, Check, AlertTriangle, ArrowLeft } from 'lucide-react';
import { getVetReport, friendlyError } from '../api';

/*
 * The pre-consultation report.
 *
 * Rendered on a WHITE sheet rather than the app's glass — this is the one
 * screen a guardian hands to (or prints for) a vet, and it should look like a
 * document, not an app. Print styles in index.css already strip the app chrome.
 *
 * Markdown is converted inline for the small subset the report emits
 * (headings, tables, lists, blockquotes, bold, rules) rather than pulling in a
 * markdown library for one screen.
 */

const esc = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const inline = (s) =>
  esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code class="px-1 py-0.5 rounded bg-slate-100 text-slate-800 text-[0.9em]">$1</code>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');

function markdownToHtml(md) {
  const lines = md.split('\n');
  const out = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Table: header row, separator, then body until a non-table line
    if (line.startsWith('|') && lines[i + 1]?.match(/^\|[\s\-|]+\|$/)) {
      const cells = (r) =>
        r.split('|').slice(1, -1).map((c) => c.trim());
      const head = cells(line);
      i += 2;
      const body = [];
      while (i < lines.length && lines[i].startsWith('|')) {
        body.push(cells(lines[i]));
        i += 1;
      }
      out.push(
        `<div class="overflow-x-auto my-4"><table class="w-full text-sm border-collapse">
          <thead><tr>${head
            .map((h) => `<th class="text-left font-bold text-slate-600 uppercase tracking-wide text-[11px] px-3 py-2 border-b-2 border-slate-300 whitespace-nowrap">${inline(h)}</th>`)
            .join('')}</tr></thead>
          <tbody>${body
            .map((row) => `<tr class="border-b border-slate-200">${row
              .map((c) => `<td class="px-3 py-2 text-slate-700 align-top whitespace-nowrap">${inline(c)}</td>`)
              .join('')}</tr>`)
            .join('')}</tbody>
        </table></div>`
      );
      continue;
    }

    if (line.startsWith('### ')) {
      out.push(`<h3 class="font-bold text-slate-800 text-base mt-5 mb-2">${inline(line.slice(4))}</h3>`);
    } else if (line.startsWith('## ')) {
      out.push(`<h2 class="font-black text-slate-900 text-xl mt-7 mb-2 pb-1 border-b border-slate-200">${inline(line.slice(3))}</h2>`);
    } else if (line.startsWith('# ')) {
      out.push(`<h1 class="font-black text-slate-900 text-2xl mb-1">${inline(line.slice(2))}</h1>`);
    } else if (line.startsWith('> ')) {
      out.push(`<blockquote class="border-l-4 border-slate-300 bg-slate-50 pl-4 pr-3 py-2 my-3 text-slate-600 text-sm italic">${inline(line.slice(2))}</blockquote>`);
    } else if (line.startsWith('- ')) {
      const items = [];
      while (i < lines.length && lines[i].startsWith('- ')) {
        items.push(`<li class="text-slate-700 text-sm mb-1">${inline(lines[i].slice(2))}</li>`);
        i += 1;
      }
      out.push(`<ul class="list-disc pl-5 my-2">${items.join('')}</ul>`);
      continue;
    } else if (line.trim() === '---') {
      out.push('<hr class="my-6 border-slate-200" />');
    } else if (line.trim() === '') {
      // skip
    } else {
      out.push(`<p class="text-slate-700 text-sm my-2 leading-relaxed">${inline(line)}</p>`);
    }
    i += 1;
  }
  return out.join('');
}

const REASONS = [
  'Routine check-up',
  'Eating less than usual',
  'Seems in pain or uncomfortable',
  'Behaviour has changed',
  'Breathing concerns',
  'Moving differently',
];

export default function VetReport({ petId, onBack }) {
  const [reason, setReason] = useState('');
  const [markdown, setMarkdown] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const generate = (r) => {
    setLoading(true);
    getVetReport(petId, r)
      .then((md) => { setMarkdown(md); setError(null); })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { generate(''); }, [petId]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable */ }
  };

  return (
    <div className="min-h-screen px-4 py-8 md:px-6">
      <div className="max-w-3xl mx-auto">

        <div className="flex items-center justify-between gap-3 mb-4 no-print flex-wrap">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass-card hover:bg-white/25 text-white font-roboto font-medium transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <div className="flex gap-2">
            <button
              onClick={copy}
              disabled={!markdown}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass-card hover:bg-white/25 disabled:opacity-40 text-white font-roboto font-medium transition-colors"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button
              onClick={() => window.print()}
              disabled={!markdown}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/35 hover:bg-white/45 disabled:opacity-40 text-white font-roboto font-bold transition-colors"
            >
              <Printer className="w-4 h-4" /> Print / PDF
            </button>
          </div>
        </div>

        {/* Reason for visit — becomes the first line of the report */}
        <div className="glass-card rounded-2xl p-4 mb-4 no-print">
          <p className="font-roboto text-white/80 text-sm mb-2">
            Why are you seeing the vet? (optional — helps them focus)
          </p>
          <div className="flex flex-wrap gap-2 mb-3">
            {REASONS.map((r) => (
              <button
                key={r}
                onClick={() => { setReason(r); generate(r); }}
                className={`px-3 py-1.5 rounded-full text-xs font-roboto font-medium transition-colors ${
                  reason === r
                    ? 'bg-white/35 text-white ring-1 ring-white/60'
                    : 'bg-white/15 text-white/75 hover:bg-white/25'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && generate(reason)}
              placeholder="Or describe it in your own words…"
              className="flex-1 min-w-0 px-4 py-2.5 rounded-xl bg-white/20 border border-white/30 text-white placeholder-white/50 font-roboto text-sm focus:outline-none focus:border-white/60"
            />
            <button
              onClick={() => generate(reason)}
              className="px-4 py-2.5 rounded-xl bg-white/25 hover:bg-white/35 text-white font-roboto font-medium text-sm transition-colors whitespace-nowrap"
            >
              Update
            </button>
          </div>
        </div>

        {error && (
          <div className="glass-card rounded-2xl p-5 border-2 border-amber-500/50 flex gap-3 no-print">
            <AlertTriangle className="w-5 h-5 text-amber-300 flex-none mt-0.5" />
            <p className="font-roboto text-white/90">{error}</p>
          </div>
        )}

        {/* The document itself — white sheet, print-friendly */}
        {loading && !markdown ? (
          <div className="glass-card rounded-2xl p-10 text-center">
            <p className="font-roboto text-white/60">Building report…</p>
          </div>
        ) : markdown ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl p-6 md:p-10 shadow-2xl"
            style={{ opacity: loading ? 0.6 : 1 }}
          >
            <div dangerouslySetInnerHTML={{ __html: markdownToHtml(markdown) }} />
          </motion.div>
        ) : null}

        <p className="font-roboto text-white/50 text-xs text-center mt-4 no-print">
          Observations only — this is not a diagnosis. Your vet interprets it.
        </p>
      </div>
    </div>
  );
}
