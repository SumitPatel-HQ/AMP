import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
globalThis.window = { location: { hostname: "localhost" } };
const server = await createServer({ configFile: false, server: { middlewareMode: true }, appType: 'custom' });
try {
 const { MetricsPanel } = await server.ssrLoadModule('/src/panels/MetricsPanel.tsx');
 const { Presentation } = await server.ssrLoadModule('/src/panels/panelPresentation.ts');
 const test = readFileSync('src/panels/MetricsPanel.test.tsx', 'utf8');
 const fixture = name => test.split(`const ${name} = {`)[1].split('} satisfies MetricsSchema;')[0];
 const before = Function(`return {${fixture('metricsBefore')}}`)();
 const after = { ...before, plan_id: 'PLAN-2', mission_utility: 14, plan_churn: .25, explanation_coverage: 1, planning_time_ms: 2.75 };
 const reqLiteral = test.split('const requesterMetrics: MetricsSchema = {')[1].split('\n};')[0];
 const requester = Function('metricsBefore', `return {${reqLiteral}}`)(before);
 after.requester_service = requester.requester_service;
 const node = React.createElement(Presentation, { value: {mode: 'compact', expand: () => {}} }, React.createElement(MetricsPanel, {currentPlanId: after.plan_id, metrics: after, diff: {metrics_before:before,metrics_after:after,request_pool_mismatch:false}, plans: []}));
 const cssName = readdirSync('dist/assets').find(n => n.startsWith('index-') && n.endsWith('.css'));
 const css = readFileSync(`dist/assets/${cssName}`, 'utf8');
 const script = `document.querySelectorAll('details').forEach(d=>d.open=true);const results=[];const wrapper=document.querySelector('#wrapper');for(const width of [340,365,390]){wrapper.style.width=width+'px';const root=document.querySelector('.compact-evaluation');const rect=root.getBoundingClientRect();const overflow=[...root.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>rect.right+1||e.scrollWidth>e.clientWidth+1).map(e=>e.tagName+'.'+e.className);results.push({width,contentWidth:root.clientWidth,overflow});}document.querySelector('#result').textContent=JSON.stringify(results);`;
 writeFileSync('.tmp-compact-check/panel.html',`<!doctype html><html><head><meta charset="utf-8"><style>${css} body{margin:0;background:var(--amis-bg)} #wrapper{width:365px;padding:8px;box-sizing:border-box}</style></head><body><div id="wrapper" class="amis-inspector-panel">${renderToStaticMarkup(node)}</div><pre id="result"></pre><script>${script}</script></body></html>`);
} finally { await server.close(); }

