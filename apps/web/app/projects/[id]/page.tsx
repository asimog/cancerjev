"use client";
import {use, useState} from "react";
import Link from "next/link";
export default function Project({params}:{params:Promise<{id:string}>}) {
  const {id:project}=use(params); const [id,setId]=useState(""); const [error,setError]=useState("");
  async function freeze(){ setError(""); const r=await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/v1/snapshots/logical`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({project_id:project})}); if(!r.ok){setError(await r.text());return} setId((await r.json()).snapshot_id); }
  return <main><p className="eyebrow">FROZEN SOURCE DATA</p><h1>{project}</h1><p>Freeze the current open GDC file universe. CancerJev records exact UUIDs, checksums, biological identity links and coverage.</p><button onClick={freeze}>Create logical snapshot</button>{id&&<p>Snapshot created: <strong>{id}</strong></p>}{error&&<pre>{error}</pre>}<p><Link href="/">← Projects</Link></p></main>;
}
