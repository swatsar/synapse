import pytest
from synapse.browser import BrowserSession, CapabilityDenied, CapabilityGuard, GuardedBrowserBackend
from synapse.computer_use import GuardedComputerUseBackend
class B:
 async def open(self,o,u): return BrowserSession('s',o,u)
 async def read(self,s): return {'url':s.url}
class C:
 async def screen_read(self): return {'pixels':1}
 async def keyboard(self,t): self.text=t
@pytest.mark.asyncio
async def test_browser_and_computer_are_capability_gated():
 async def check(**kw): return type('R',(),{'approved':kw['required'] in {'browser:read','computer:screen.read'}})()
 guard=CapabilityGuard(check); browser=GuardedBrowserBackend(B(),guard)
 with pytest.raises(CapabilityDenied): await browser.open('a','https://x')
 session=await GuardedBrowserBackend(B(),CapabilityGuard(lambda **kw: check(required='browser:read'))).read(BrowserSession('s','a','https://x'))
 assert session['url']=='https://x'
 computer=GuardedComputerUseBackend(C(),guard); assert await computer.screen_read()=={'pixels':1}
 with pytest.raises(CapabilityDenied): await computer.keyboard('x')
