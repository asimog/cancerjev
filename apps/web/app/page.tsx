type Project = {project_id:string; name?:string; primary_site?:string[]};
export const dynamic = "force-dynamic";
async function projects(): Promise<Project[]> {
  const base = process.env.API_INTERNAL_URL ?? "http://api:8000";
  const response = await fetch(`${base}/v1/gdc/projects?size=100`, {next:{revalidate:300}});
  if (!response.ok) throw new Error("GDC projects are temporarily unavailable");
  return (await response.json()).data.hits;
}
export default async function Home() {
  const rows = await projects();
  return <main><header><p className="eyebrow">CANCERJEV · SOURCE DATA</p><h1>Open TCGA projects</h1><p>Choose a real GDC project to begin a reproducible research workflow.</p></header><section><table><thead><tr><th>Project</th><th>Name</th><th>Primary site</th><th>Action</th></tr></thead><tbody>{rows.filter(x=>x.project_id.startsWith("TCGA-")).map(x=><tr key={x.project_id}><td><strong>{x.project_id}</strong></td><td>{x.name}</td><td>{x.primary_site?.join(", ")}</td><td><a href={`/projects/${x.project_id}`}>Inspect</a></td></tr>)}</tbody></table></section></main>;
}
