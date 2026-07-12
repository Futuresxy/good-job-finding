const REPO="Futuresxy/good-job-finding";
const PATH="config/custom_sources.json";
let accessToken="";
let task={company:"",url:"",action:"upsert"};
const $=id=>document.getElementById(id);
const channel=new BroadcastChannel("gjf-repository-sync");

function readTask(value){
  const params=value instanceof URLSearchParams?value:new URLSearchParams(value);
  const company=(params.get("company")||"").trim();
  const url=(params.get("url")||"").trim();
  const action=params.get("action")==="remove"?"remove":"upsert";
  if(company&&(action==="remove"||isUrl(url))){task={company,url,action};renderTask();if(accessToken)writeSource()}
}
function isUrl(value){try{return ["http:","https:"].includes(new URL(value).protocol)}catch{return false}}
function renderTask(){$("company").textContent=task.company||"等待公司信息";$("url").textContent=task.action==="remove"?"从重点公司移除，并停止每日监测":task.url||"--"}
function decode(value){return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(value.replace(/\n/g,"")),c=>c.charCodeAt(0))))}
function encode(value){const bytes=new TextEncoder().encode(JSON.stringify(value,null,2)+"\n");let binary="";bytes.forEach(byte=>binary+=String.fromCharCode(byte));return btoa(binary)}
function status(text,type=""){$("status").textContent=text;$("status").className="status "+type}

async function github(path,options={}){
  const response=await fetch("https://api.github.com/repos/"+REPO+"/contents/"+path,{...options,headers:{"Accept":"application/vnd.github+json","Authorization":"Bearer "+accessToken,"X-GitHub-Api-Version":"2022-11-28",...(options.headers||{})}});
  if(!response.ok){const detail=await response.json().catch(()=>({}));throw new Error(detail.message||("GitHub 返回 "+response.status))}
  return response.json()
}
async function writeSource(){
  if(!task.company||(task.action!=="remove"&&!isUrl(task.url))){status("公司名称或招聘网址无效。","error");return}
  const button=$("sync");button.disabled=true;button.textContent="正在写入...";
  try{
    const current=await github(PATH);
    const doc=decode(current.content);
    const sources=Array.isArray(doc.sources)?doc.sources:[];
    const removed=new Set(Array.isArray(doc.removedCompanies)?doc.removedCompanies:[]);
    if(task.action==="remove"){
      const index=sources.findIndex(source=>source.company===task.company);
      if(index>=0)sources.splice(index,1);
      removed.add(task.company);
    }else{
      const item={company:task.company,careersUrl:task.url,priority:10,enabled:true,parser:task.company==="百度"?"baidu-campus-monitor":"official-page-monitor"};
      const index=sources.findIndex(source=>source.company===task.company);
      index>=0?sources.splice(index,1,item):sources.push(item);
      removed.delete(task.company);
    }
    doc.version=1;doc.updatedAt=new Date().toISOString();doc.sources=sources;doc.removedCompanies=[...removed];
    const verb=task.action==="remove"?"Remove ":"Update ";
    await github(PATH,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:verb+task.company+" recruitment source",content:encode(doc),sha:current.sha})});
    status(task.action==="remove"?task.company+" 已从重点公司移除，后续每日任务将跳过该公司。":task.company+" 已写入仓库，将从下一次每日任务开始监测。","ok");
    button.textContent="已写入仓库";
    channel.postMessage({type:"synced",company:task.company,url:task.url,action:task.action});
  }catch(error){status(error.message+"。请确认 Token 只授权该仓库且 Contents 为 Read and write。","error");button.textContent="重试写入"}
  finally{button.disabled=false}
}
$("sync").onclick=()=>{const value=$("token").value.trim();if(value){accessToken=value;$("token").value="";$("authPanel").hidden=true}$("sync").textContent="写入仓库";if(!accessToken){status("请先填写仓库专用 Token。","error");return}writeSource()};
channel.onmessage=event=>{if(event.data?.type==="sync-source")readTask(new URLSearchParams({company:event.data.company||"",url:event.data.url||""}))};
readTask(new URLSearchParams(location.search));
renderTask();
