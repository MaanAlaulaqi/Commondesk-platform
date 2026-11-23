/* Capture authorized demo states; all output stays outside source control. */
const { chromium } = require('../web/node_modules/playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.argv[2] || 'http://localhost:5173/';
const output = path.resolve('.data/browser',new URL(base).hostname);
async function main(){
  await fs.mkdir(output,{recursive:true});
  const browser = await chromium.launch();
  try {
    for (const [name,width,height] of [['desktop',1440,1000],['phone',390,844]]) {
      const page = await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(base);
      for(const theme of ['light','dark']) {
        const lang=theme==='light'?'en':'ar';
        for(const layout of ['map','list']) {
          await page.evaluate(({theme,lang,layout})=>{
            localStorage.setItem('theme',theme);
            localStorage.setItem('language',lang);
            localStorage.setItem('layout',layout);
            sessionStorage.setItem('mobile-tab',layout);
          },{theme,lang,layout});
          const response=page.waitForResponse(r=>r.url().includes('/api/insights?') && r.ok());
          await page.reload();
          const stats=await (await response).json();
          assert.equal(stats.total,2348);
          await page.locator('.metric strong').first().waitFor();
          await page.waitForFunction(()=>document.querySelector('.metric strong')?.textContent!=='—');
          await page.waitForTimeout(500);
          assert.equal(await page.locator('html').getAttribute('dir'),lang==='ar'?'rtl':'ltr');
          assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),'Horizontal overflow');
          await page.screenshot({path:path.join(output,[name,theme,lang,layout].join('-')+'.png'),fullPage:true});
        }
      }
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('Verified eight seeded browser views, dimensions, themes, locales and layouts against',base);
  } finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
