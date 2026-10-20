import sys, os, time, asyncio, pathlib
from playwright.async_api import async_playwright
mode=sys.argv[1]  # 'stills' or 'frames'
out=pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        pg=await b.new_page(viewport={'width':1080,'height':1920})
        pg.on('pageerror',lambda e: print('pageerror',e)); pg.on('console',lambda m: print('console',m.type,m.text))
        async def three(route):
            rel=route.request.url.split('three@0.160.0/')[1]
            await route.fulfill(path=os.path.abspath('node_modules/three/'+rel),content_type='application/javascript')
        await pg.route('https://cdn.jsdelivr.net/npm/three@0.160.0/**',three)
        await pg.goto('file://'+os.path.abspath('test.html')+'#reel')
        await pg.wait_for_function('() => !!window.__reel', timeout=60000, polling=500)
        await pg.wait_for_timeout(1500)
        times=[float(x) for x in sys.argv[3].split(',')] if mode=='stills' else [i/30 for i in range(int(30*float(os.environ.get('REEL_SECS','30'))))]
        lo,hi=(int(x) for x in sys.argv[3].split('-')) if mode=='range' else (0,10**9)
        t0=time.time()
        for i,s in enumerate(times):
            if mode=='range' and not (lo<=i<=hi): continue
            if mode=='frames' and (out/f'f{i:04d}.png').exists() and i < len(times)-1 and (out/f'f{i+1:04d}.png').exists(): continue
            await pg.evaluate(f'window.__reel({s})')
            await pg.screenshot(path=str(out/(f's{s:05.1f}.png' if mode=='stills' else f'f{i:04d}.png')), timeout=120000)
            if i%60==0: print(i, round(time.time()-t0,1), flush=True)
        await b.close()
asyncio.run(main())
