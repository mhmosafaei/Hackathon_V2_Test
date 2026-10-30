import {test,expect,vi,afterEach} from 'vitest';
import {scrollToPermitSection} from './App.jsx';
afterEach(()=>{document.body.innerHTML='';vi.restoreAllMocks();vi.unstubAllGlobals();});
test.each(['key-permit-limits','condition-overview'])('positions %s below the actual sticky header',id=>{
 document.body.innerHTML=`<header class="header" style="position:sticky"></header><section id="${id}"></section>`;
 const header=document.querySelector('.header'),target=document.getElementById(id);
 vi.spyOn(header,'getBoundingClientRect').mockReturnValue({height:154});
 vi.spyOn(target,'getBoundingClientRect').mockReturnValue({top:800});
 vi.stubGlobal('scrollY',200);
 const scroll=vi.spyOn(window,'scrollTo').mockImplementation(()=>{});
 scrollToPermitSection(id);
 expect(scroll).toHaveBeenLastCalledWith({top:830,behavior:'smooth'});
 // A resized header must be measured again rather than using a fixed offset.
 vi.spyOn(header,'getBoundingClientRect').mockReturnValue({height:96});
 scrollToPermitSection(id);
 expect(scroll).toHaveBeenLastCalledWith({top:888,behavior:'smooth'});
});
