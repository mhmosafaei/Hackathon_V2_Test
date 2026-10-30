import {explicitUtc} from './environmentDefaults.js';

const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const pad=value=>String(value).padStart(2,'0');
function parsed(value){const normalized=explicitUtc(value);return normalized ? new Date(normalized+'Z') : null;}
export function decisionTime(value){
  const date=parsed(value);
  if(!date)return 'Not available';
  const seconds=date.getUTCSeconds() ? ':'+pad(date.getUTCSeconds()) : '';
  return `${pad(date.getUTCDate())} ${months[date.getUTCMonth()]} ${date.getUTCFullYear()} · ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}${seconds} UTC`;
}
export function timelineTicks(timeline=[]){
  const first=parsed(timeline[0]?.start),last=parsed(timeline.at(-1)?.end);
  if(!first || !last || last<=first)return [];
  const span=last-first,steps=span>48*3600000 ? 6 : 4;
  return Array.from({length:steps+1},(_,index)=>{
    const date=new Date(first.valueOf()+span*index/steps);
    return {time:date.toISOString(),position:index/steps*100,date:`${pad(date.getUTCDate())} ${months[date.getUTCMonth()]}`,
      clock:`${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`,secondary:index%2===1};
  });
}
