const state={jobs:[],profile:null,watch:new Set(JSON.parse(localStorage.getItem("gjf-watch")||"null")||[]),favorites:new Set(JSON.parse(localStorage.getItem("gjf-favorites")||"[]")),resumeText:localStorage.getItem("gjf-resume-text")||"",selectedDirections:new Set(),selectedCompany:null,showFavorites:false,companyPage:1,pageSize:6};
const $=(id)=>document.getElementById(id);
const esc=(v)=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const norm=(v)=>String(v??"").toLowerCase().replace(/\s+/g,"");
async function init(){
  try{
    const [jobs,profile,status]=await Promise.all(["data/jobs.json","config/profile.json","data/status.json"].map(p=>fetch(p+"?v="+Date.now()).then(r=>{if(!r.ok)throw new Error(p);return r.json()})));
    state.jobs=jobs.jobs||[];state.profile=profile;
    if(!state.watch.size) profile.watchCompanies.forEach(x=>state.watch.add(x));
    renderDirections();renderCities();bind();renderCompanies();renderJobs();renderStatus(status,jobs);
    if(state.resumeText) analyzeResume(state.resumeText,"上次分析的简历");
  }catch(error){$("runState").textContent="数据读取失败";$("jobList").innerHTML='<div class="empty-state">暂时无法读取岗位数据，请稍后刷新。</div>'}
  window.lucide?.createIcons();
}
function bind(){
  ["searchInput","batchFilter","cityFilter","watchOnly","verifiedOnly","sortBy"].forEach(id=>$(id).addEventListener(id==="searchInput"?"input":"change",()=>{state.companyPage=1;renderJobs()}));
  $("resetFilters").onclick=()=>{["searchInput","batchFilter","cityFilter"].forEach(id=>$(id).value="");$("watchOnly").checked=false;$("verifiedOnly").checked=false;state.selectedDirections.clear();state.selectedCompany=null;state.showFavorites=false;state.companyPage=1;document.querySelectorAll("[data-direction]").forEach(x=>x.checked=false);renderJobs()};$("backCompanies").onclick=()=>{state.selectedCompany=null;state.showFavorites=false;state.companyPage=1;renderJobs();location.hash="radar"};const openFavorites=()=>{state.selectedCompany=null;state.showFavorites=true;renderJobs();location.hash="radar"};$("favoritesNav").onclick=openFavorites;$("favoritesToolbar").onclick=openFavorites;
  $("addCompanyForm").onsubmit=e=>{e.preventDefault();const name=$("companyInput").value.trim();if(name){state.watch.add(name);saveWatch();$("companyInput").value="";renderCompanies();renderJobs()}};
  $("resumeFile").onchange=readResume;
  $("closeJob").onclick=()=>$("jobDialog").close();
  $("openClawSetup").onclick=()=>{$("openClawDialog").showModal();window.lucide?.createIcons()};
  $("closeOpenClaw").onclick=()=>$("openClawDialog").close();
}
function renderDirections(){
  $("directionFilters").innerHTML=state.profile.directions.map(d=>'<label class="check-item"><input type="checkbox" data-direction="'+esc(d.id)+'"><span>'+esc(d.label)+'</span></label>').join("");
  document.querySelectorAll("[data-direction]").forEach(x=>x.onchange=()=>{x.checked?state.selectedDirections.add(x.dataset.direction):state.selectedDirections.delete(x.dataset.direction);state.companyPage=1;renderJobs()});
}
function renderCities(){
  const cities=[...new Set([...state.profile.preferredCities,...state.jobs.map(j=>j.city)])].filter(Boolean);
  $("cityFilter").innerHTML='<option value="">全部城市</option>'+cities.map(c=>'<option>'+esc(c)+'</option>').join("");
}
function renderStatus(status,data){
  $("runState").textContent=data.mode==="demo"?"演示数据 · 等待正式采集":"每日采集已运行";
  $("runTime").textContent="最近更新 "+new Date(data.generatedAt).toLocaleString("zh-CN");
  $("metricOpen").textContent=state.jobs.filter(j=>j.status==="已开启").length;
  $("metricPending").textContent=state.jobs.filter(j=>j.status==="待核验").length;
  $("metricCompanies").textContent=state.watch.size;
  const notice=$("dataNotice");notice.hidden=data.mode!=="demo";notice.textContent=data.disclaimer||"";
}
function calculateMatch(job){
  const chosen=state.selectedDirections.size?state.selectedDirections:new Set(state.profile.directions.map(d=>d.id));
  const dirHits=(job.directionIds||[]).filter(id=>chosen.has(id)).length;
  let score=Math.min(55,dirHits*25);
  if(state.watch.has(job.company))score+=15;
  if(state.profile.preferredCities.includes(job.city))score+=5;
  const resume=norm(state.resumeText);
  const skillHits=(job.skills||[]).filter(s=>resume&&resume.includes(norm(s))).length;
  score+=Math.min(25,skillHits*6);
  return Math.min(99,score||10);
}
function batchKind(job){return job.batch==="正式批"?"formal":["人才计划","提前批","专项计划"].includes(job.batch)?"early":"other"}
function matchesBatch(job,value){return !value||batchKind(job)===value}
function filteredJobs(){
  const q=norm($("searchInput").value),batch=$("batchFilter").value,city=$("cityFilter").value;
  return state.jobs.filter(j=>{
    if(j.batch==="实习生")return false;
    const hay=norm([j.company,j.title,j.city,...(j.skills||[]),...(j.requirements||[])].join(" "));
    return(!q||hay.includes(q))&&matchesBatch(j,batch)&&(!city||j.city===city)&&(!$("watchOnly").checked||state.watch.has(companyGroup(j)))&&(!$("verifiedOnly").checked||j.status==="已开启")&&(!state.selectedDirections.size||(j.directionIds||[]).some(id=>state.selectedDirections.has(id)));
  }).map(j=>({...j,match:calculateMatch(j)})).sort((a,b)=>$("sortBy").value==="company"?a.company.localeCompare(b.company):$("sortBy").value==="checked"?new Date(b.lastChecked)-new Date(a.lastChecked):b.match-a.match);
}
function companyGroup(job){return job.companyGroup||String(job.company).replace(/\s+Seed$/,"")}
function isOpen(job){return job.status==="已开启"}
function batchState(jobs,kind){return jobs.some(j=>batchKind(j)===kind&&isOpen(j))}
function renderJobs(){
  if(!state.profile)return;
  updateFavoriteCount();
  const all=filteredJobs();
  $("metricMatched").textContent=all.length;
  $("companyPagination").hidden=true;
  if(state.showFavorites){renderFavorites(all);return}
  if(!state.selectedCompany){renderCompanyOverview(all);return}
  renderCompanyJobs(all);
}
function renderCompanyJobs(all){
  const jobs=all.filter(j=>companyGroup(j)===state.selectedCompany);
  const statusJobs=state.jobs.filter(j=>j.batch!=="实习生"&&companyGroup(j)===state.selectedCompany);
  $("viewEyebrow").textContent="MATCHED JOBS";$("viewTitle").textContent=state.selectedCompany+" · 适配岗位";$("backCompanies").hidden=false;
  const early=batchState(statusJobs,"early"),formal=batchState(statusJobs,"formal");
  $("resultsSummary").textContent="提前批（顶尖人才）："+(early?"已开启":"持续监测")+"；正式批："+(formal?"已开启":"持续监测")+"。当前筛选下 "+jobs.length+" 个适配岗位。";
  $("jobList").className="job-list";
  $("jobList").innerHTML=jobs.length?jobs.map(jobCardHtml).join(""):'<div class="empty-state"><strong>暂未发现符合条件的岗位</strong><p>该公司仍在每日监测；也可以返回公司总览调整方向或批次。</p></div>';
  bindJobCards();
}
function renderFavorites(){
  const jobs=state.jobs.filter(j=>j.batch!=="实习生"&&state.favorites.has(j.id)).map(j=>({...j,match:calculateMatch(j)})).sort((a,b)=>b.match-a.match);
  $("viewEyebrow").textContent="SAVED JOBS";$("viewTitle").textContent="重点关注岗位";$("backCompanies").hidden=false;
  $("resultsSummary").textContent="已收藏 "+jobs.length+" 个岗位。这里集中记录状态、截止时间和投递入口。";
  $("jobList").className="job-list";
  $("jobList").innerHTML=jobs.length?jobs.map(jobCardHtml).join(""):'<div class="empty-state"><strong>还没有收藏岗位</strong><p>进入公司岗位页，点击书签按钮加入重点关注。</p></div>';
  bindJobCards();
}
function jobCardHtml(j){
  const saved=state.favorites.has(j.id);
  return '<article class="job-card '+(j.status==="待核验"?"pending":"")+'" data-job="'+esc(j.id)+'" tabindex="0"><div><div class="job-title"><h3>'+esc(j.title)+'</h3><span class="tag '+(j.status==="待核验"?"neutral":"")+'">'+esc(j.status)+'</span><button class="favorite-button '+(saved?"is-saved":"")+'" type="button" data-favorite="'+esc(j.id)+'" title="'+(saved?"取消收藏":"收藏岗位")+'" aria-label="'+(saved?"取消收藏":"收藏岗位")+'"><i data-lucide="bookmark"></i></button></div><p><strong>'+esc(j.company)+'</strong> · '+esc(j.batch)+' · '+esc((j.requirements||[]).slice(0,2).join("；"))+'</p><div class="job-meta"><span><i data-lucide="map-pin"></i>'+esc(j.city)+'</span><span><i data-lucide="calendar-clock"></i>'+(j.deadline?esc(j.deadline)+" 截止":"截止时间待确认")+'</span><span><i data-lucide="refresh-cw"></i>'+new Date(j.lastChecked).toLocaleDateString("zh-CN")+'</span></div></div><div class="job-skills">'+(j.skills||[]).slice(0,5).map(s=>'<span class="tag">'+esc(s)+'</span>').join("")+'</div><div class="match-score"><strong>'+j.match+'%</strong><span>匹配</span></div><div class="job-actions">'+(j.status==="已开启"&&j.applyUrl?'<a href="'+esc(j.applyUrl)+'" target="_blank" rel="noreferrer">立即投递</a>':'<button type="button">查看状态</button>')+'</div></article>'
}
function bindJobCards(){
  document.querySelectorAll("[data-job]").forEach(el=>{el.onclick=e=>{if(!e.target.closest("a,button"))openJob(el.dataset.job)};el.onkeydown=e=>{if(e.key==="Enter")openJob(el.dataset.job)}});
  document.querySelectorAll("[data-favorite]").forEach(button=>button.onclick=e=>{e.stopPropagation();toggleFavorite(button.dataset.favorite)});
  window.lucide?.createIcons();
}
function toggleFavorite(id){
  state.favorites.has(id)?state.favorites.delete(id):state.favorites.add(id);
  localStorage.setItem("gjf-favorites",JSON.stringify([...state.favorites]));
  updateFavoriteCount();renderJobs();
}
function updateFavoriteCount(){$("favoriteCount").textContent=state.favorites.size}
function renderCompanyOverview(matchingJobs){
  const q=norm($("searchInput").value);
  const knownGroups=new Set(state.jobs.filter(j=>j.batch!=="实习生").map(companyGroup));
  const names=[...new Set([...(state.profile.watchCompanies||[]),...state.watch,...knownGroups])].filter(name=>!q||norm(name).includes(q)||matchingJobs.some(j=>companyGroup(j)===name));
  const companies=names.map(name=>{
    const statusJobs=state.jobs.filter(j=>j.batch!=="实习生"&&companyGroup(j)===name);
    const matches=matchingJobs.filter(j=>companyGroup(j)===name);
    const directionSource=matches.length?matches:statusJobs;
    return {name,statusJobs,matches,early:batchState(statusJobs,"early"),formal:batchState(statusJobs,"formal"),maxMatch:Math.max(0,...matches.map(j=>j.match),...statusJobs.map(calculateMatch)),directions:new Set(directionSource.flatMap(j=>j.directionIds||[]))};
  }).sort((a,b)=>(Number(b.formal)*3+Number(b.early)*2)-(Number(a.formal)*3+Number(a.early)*2)||b.maxMatch-a.maxMatch||a.name.localeCompare(b.name));
  const openCompanies=companies.filter(c=>c.early||c.formal).length;
  const totalPages=Math.max(1,Math.ceil(companies.length/state.pageSize));state.companyPage=Math.min(state.companyPage,totalPages);
  const pageItems=companies.slice((state.companyPage-1)*state.pageSize,state.companyPage*state.pageSize);
  $("viewEyebrow").textContent="COMPANY RADAR";$("viewTitle").textContent="2027 秋招重点公司";$("backCompanies").hidden=true;
  $("resultsSummary").textContent="固定监测 "+companies.length+" 家重点公司；"+openCompanies+" 家已开启提前批或正式批。实习岗位不纳入当前关注。";
  $("jobList").className="company-grid";
  $("jobList").innerHTML=pageItems.map(c=>{
    const labels=[...c.directions].map(id=>state.profile.directions.find(d=>d.id===id)?.label).filter(Boolean).slice(0,3);
    const topStatus=c.formal?"正式批已开启":c.early?"提前批已开启":"持续监测";
    return '<button class="company-card '+(c.formal||c.early?"is-open":"is-watching")+'" type="button" data-company="'+esc(c.name)+'"><span class="company-card-head"><span><small>'+esc(topStatus)+'</small><strong>'+esc(c.name)+'</strong></span><span class="company-match">'+c.maxMatch+'%</span></span><span class="batch-statuses">'+batchBadge("early",c.early)+batchBadge("formal",c.formal)+'</span><span class="company-directions">'+(labels.length?labels.map(x=>'<span>'+esc(x)+'</span>').join(""):'<span>暂未发现方向匹配岗位</span>')+'</span><span class="company-card-foot"><span>'+c.matches.length+' 个匹配岗位</span><span>查看岗位 <i data-lucide="arrow-right"></i></span></span></button>'
  }).join("");
  document.querySelectorAll("[data-company]").forEach(el=>el.onclick=()=>{state.selectedCompany=el.dataset.company;state.showFavorites=false;renderJobs();location.hash="radar"});
  renderPagination(totalPages);window.lucide?.createIcons();
}
function batchBadge(kind,open){
  const label=kind==="early"?"提前批（顶尖人才）":"正式批";
  return '<span class="batch-badge '+(open?"is-open":"is-monitoring")+'"><i data-lucide="'+(open?"circle-check":"radar")+'"></i><span>'+label+'</span><small>'+(open?"已开启":"持续监测")+'</small></span>'
}
function renderPagination(totalPages){
  const pager=$("companyPagination");pager.hidden=totalPages<=1;
  if(totalPages<=1){pager.innerHTML="";return}
  pager.innerHTML='<button type="button" id="prevCompanyPage" title="上一页" aria-label="上一页" '+(state.companyPage===1?"disabled":"")+'><i data-lucide="chevron-left"></i></button><span>第 '+state.companyPage+' / '+totalPages+' 页</span><button type="button" id="nextCompanyPage" title="下一页" aria-label="下一页" '+(state.companyPage===totalPages?"disabled":"")+'><i data-lucide="chevron-right"></i></button>';
  $("prevCompanyPage").onclick=()=>{state.companyPage=Math.max(1,state.companyPage-1);renderJobs();location.hash="radar"};
  $("nextCompanyPage").onclick=()=>{state.companyPage=Math.min(totalPages,state.companyPage+1);renderJobs();location.hash="radar"};
}
function openJob(id){
  const j=state.jobs.find(x=>x.id===id);if(!j)return;
  $("dialogCompany").textContent=j.company+" · "+j.batch+" · "+j.status;$("dialogTitle").textContent=j.title;
  $("jobDetail").innerHTML='<div class="detail-grid"><section class="detail-block"><h3>岗位要求</h3><ul>'+j.requirements.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul></section><section class="detail-block"><h3>笔试面试流程</h3><ol>'+j.process.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ol></section><section class="detail-block"><h3>技能关键词</h3><div class="tag-cloud">'+j.skills.map(x=>'<span>'+esc(x)+'</span>').join("")+'</div></section><section class="detail-block"><h3>时间与证据</h3><p>发布时间：'+esc(j.postedAt||"待确认")+'<br>截止时间：'+esc(j.deadline||"待确认")+'<br>最近检查：'+new Date(j.lastChecked).toLocaleString("zh-CN")+'<br>可信度：'+Math.round((j.confidence||0)*100)+'%</p></section></div><section class="detail-block"><h3>核验依据</h3><p>'+esc(j.evidence||"以官方招聘页实时信息为准")+'</p><p><strong>本次变化：</strong>'+esc(j.change||"首次记录")+'</p></section><div class="detail-actions">'+(j.status==="已开启"&&j.applyUrl?'<a href="'+esc(j.applyUrl)+'" target="_blank" rel="noreferrer">立即投递</a>':'')+'<a class="source-link" href="'+esc(j.announcementUrl||j.sourceUrl)+'" target="_blank" rel="noreferrer">查看官方依据</a></div>';
  $("jobDialog").showModal();
}
function renderCompanies(){
  $("companyList").innerHTML=[...state.watch].sort((a,b)=>a.localeCompare(b)).map(c=>'<span class="company-item">'+esc(c)+'<button data-remove="'+esc(c)+'" title="取消关注" aria-label="取消关注 '+esc(c)+'"><i data-lucide="x"></i></button></span>').join("");
  document.querySelectorAll("[data-remove]").forEach(b=>b.onclick=()=>{state.watch.delete(b.dataset.remove);saveWatch();renderCompanies();renderJobs()});
  $("metricCompanies").textContent=state.watch.size;window.lucide?.createIcons();
}
function saveWatch(){localStorage.setItem("gjf-watch",JSON.stringify([...state.watch]))}
async function readResume(e){
  const file=e.target.files?.[0];if(!file)return;
  try{
    let text="";
    if(file.type==="application/pdf"||file.name.toLowerCase().endsWith(".pdf"))text=await extractPdf(file);else text=await file.text();
    if(text.trim().length<80)throw new Error("简历文本过少");
    state.resumeText=text;localStorage.setItem("gjf-resume-text",text);analyzeResume(text,file.name);renderJobs();
  }catch(err){$("resumeEmpty").innerHTML='<i data-lucide="file-warning"></i><h3>暂时无法读取这份简历</h3><p>'+esc(err.message||"请改用文本型 PDF、TXT 或 Markdown。")+'</p>';window.lucide?.createIcons()}
}
async function extractPdf(file){
  const pdfjs=window.pdfjsLib||await import("https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc="https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs";
  const pdf=await pdfjs.getDocument({data:await file.arrayBuffer()}).promise;let text="";
  for(let i=1;i<=pdf.numPages;i++){const page=await pdf.getPage(i),content=await page.getTextContent();text+=content.items.map(x=>x.str).join(" ")+"\n"}return text;
}
function analyzeResume(text,name){
  const n=norm(text),all=[...new Set(state.profile.directions.flatMap(d=>d.keywords))],hits=all.filter(k=>n.includes(norm(k)));
  const dirScores=state.profile.directions.map(d=>({label:d.label,hits:d.keywords.filter(k=>n.includes(norm(k)))})).sort((a,b)=>b.hits.length-a.hits.length);
  const score=Math.min(100,Math.round(hits.length/Math.max(10,all.length*.22)*100));
  $("resumeEmpty").hidden=true;$("resumeReport").hidden=false;$("resumeScore").textContent=score;$("resumeName").textContent=name;
  $("resumeSummary").textContent=dirScores[0].hits.length?"当前最强方向："+dirScores[0].label+"；识别到 "+hits.length+" 个相关能力关键词。":"尚未识别到足够的目标方向关键词，建议补充项目成果与技术细节。";
  $("resumeSkills").innerHTML=(hits.length?hits:["暂未识别"]).map(x=>'<span>'+esc(x)+'</span>').join("");
  const gaps=dirScores.slice(0,3).flatMap(d=>d.hits.length<2?["为“"+d.label+"”补充可验证的项目、指标或实验结果"]:[]).concat(["用“问题—行动—量化结果”重写最相关的两个项目","为每项核心技能准备原理、实现、性能与故障排查追问"]).slice(0,4);
  $("resumeGaps").innerHTML=gaps.map(x=>'<li>'+esc(x)+'</li>').join("");
  const top=state.jobs.map(j=>({...j,match:calculateMatch(j)})).sort((a,b)=>b.match-a.match).slice(0,2);
  const qs=top.flatMap(j=>["围绕“"+j.title+"”，你最匹配的项目是哪一个？请用 3 分钟讲清目标、设计和量化结果。",questionFor(j),...j.skills.filter(s=>!n.includes(norm(s))).slice(0,1).map(s=>"岗位需要 "+s+"，请准备它的核心原理、使用场景和一次实际问题排查。")]).slice(0,6);
  $("interviewQuestions").innerHTML=qs.map((q,i)=>'<div class="question"><strong>Q'+(i+1)+'</strong> '+esc(q)+'</div>').join("");
}
function questionFor(job){
  if(job.directionIds.includes("ai-infra"))return"如何分析大模型推理的吞吐、首 Token 延迟和显存占用？你会从哪里开始优化？";
  if(job.directionIds.includes("architecture"))return"请说明一次微架构性能瓶颈分析：指标、模型、实验与结论分别是什么？";
  if(job.directionIds.includes("chip-design"))return"从规格到 RTL，再到验证与时序收敛，你参与过的模块如何完成闭环？";
  return"请解释一个你深入理解的系统模块，并说明关键权衡与失败方案。";
}
init();