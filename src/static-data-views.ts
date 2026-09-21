/** Data visualisations inside the existing constrained reader. No WebGL imports. */
import { artifactPath, fetchPlotObject, plotFigure, smallJson } from './plot-view';
import { boundedBody } from './delivery-policy';
import type { ReleaseManifest } from './types';

export function mountStaticDataViews(host: HTMLElement) {
  const heading=document.createElement('h2'); heading.textContent='Visualise published data';
  const note=document.createElement('p'); note.textContent='Small orbit plots and dated globe/transit pictures. Load only what you choose; nothing animates or refreshes automatically.';
  const form=document.createElement('form');
  const label=document.createElement('label'); label.textContent='Satellite NORAD number ';
  const input=document.createElement('input'); input.type='number'; input.min='1'; input.required=true; input.value='25544'; label.append(input);
  const plotButton=document.createElement('button'); plotButton.textContent='Load small orbit plot'; plotButton.type='submit';
  const figureButton=document.createElement('button'); figureButton.type='button'; figureButton.textContent='Load globe and transit snapshots';
  const status=document.createElement('p'); status.setAttribute('role','status');
  const plots=document.createElement('div'); const figures=document.createElement('div');
  plots.dataset.savedVisual='true'; figures.dataset.savedVisual='true';
  form.append(label,plotButton); host.append(heading,note,form,figureButton,status,plots,figures);
  let manifest: ReleaseManifest | null=null;
  const getManifest=async () => {
    if (!manifest) {
      const v=await smallJson('data/manifest.json') as ReleaseManifest;
      if (typeof v.release!=='string') throw Error('Published release unavailable');
      manifest=v;
    }
    return manifest;
  };
  form.addEventListener('submit', async event=>{
    event.preventDefault(); plotButton.disabled=true; plots.replaceChildren(); status.textContent='Loading the selected plot…';
    try {
      const id=Number(input.value); if (!Number.isInteger(id) || id<1) throw Error('Enter a NORAD number');
      const m=await getManifest(); const ref=m.orbitPlotViews?.objects.find(r=>r.norad===id);
      if (!ref) {
        status.textContent='No small plot is published for this object in this release. No large archive was loaded.';
        const shard=m.orbitHistory?.shards.find(r=>r.shard===id%m.orbitHistory!.shardCount);
        if (shard) {
          const full=document.createElement('a'); full.href=artifactPath(shard.path); full.setAttribute('download','');
          full.textContent='Full-resolution archive JSON (large download)'; plots.append(full);
        }
        return;
      }
      const record=await fetchPlotObject(artifactPath(ref.path));
      if (record.norad!==id) throw Error('Published object does not match selection');
      const stamp=document.createElement('p'); stamp.textContent=`Archive edition: ${m.orbitPlotViews?.generatedAt ?? 'unavailable'}. Not live.`;
      plots.append(stamp,plotFigure(record)); status.textContent='Small plot loaded. Full-resolution data remains available at the plot.';
    } catch (error) { status.textContent=`Plot unavailable. ${String(error)}`; }
    finally { plotButton.disabled=false; }
  });
  figureButton.addEventListener('click',async ()=>{
    figureButton.disabled=true; figures.replaceChildren(); status.textContent='Loading published snapshots…';
    try {
      const m=await getManifest(); const refs=m.staticFigures?.figures;
      if (!refs?.length) throw Error('No globe/transit snapshots are published in this release yet.');
      for (const kind of ['globe','transit']) {
        const ref=refs.find(r=>r.kind===kind); if (!ref) throw Error(`Missing ${kind} snapshot`);
        const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),30000);
        let bytes: Uint8Array;
        try {
          const response=await fetch(new URL(artifactPath(ref.path),document.baseURI),{signal:controller.signal,redirect:'error'});
          bytes=await boundedBody(response,1024*1024);
        } finally { clearTimeout(timer); }
        const text=new TextDecoder().decode(bytes);
        if (!text.startsWith('<svg') || !text.includes(m.staticFigures!.generatedAt)) throw Error('Snapshot timestamp missing');
        const fig=document.createElement('figure'); const caption=document.createElement('figcaption');
        caption.textContent=`${kind==='globe'?'Globe':'Transit'} snapshot · ${m.staticFigures!.generatedAt} · not live. Limitations and evidence class are printed in the figure.`;
        const img=document.createElement('img'); img.alt=caption.textContent; img.style.cssText='display:block;width:100%;height:auto';
        // SVG is rendered as an image, never inserted as executable markup. The
        // self-contained data URL also survives Save offline copy.
        img.src=`data:image/svg+xml;charset=utf-8,${encodeURIComponent(text)}`;
        fig.append(img,caption); figures.append(fig);
      }
      status.textContent='Snapshots loaded. They show their published times and do not update automatically.';
    } catch(error) { status.textContent=`Snapshots unavailable or incomplete. ${String(error)}`; figureButton.disabled=false; }
  });
}
