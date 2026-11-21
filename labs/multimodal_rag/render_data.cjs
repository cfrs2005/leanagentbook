// Render only original SVG assets. Install the pinned renderer outside the repository.
const fs = require('node:fs');
const path = require('node:path');
const { Resvg } = require(process.env.RESVG_MODULE || '/tmp/leanagentbook-svg-preview/node_modules/@resvg/resvg-js');
const dir = path.join(__dirname, 'data', 'images');
for (const name of fs.readdirSync(dir).filter(name => name.endsWith('.svg')).sort()) {
  fs.writeFileSync(path.join(dir, name.replace(/\.svg$/, '.png')),
    new Resvg(fs.readFileSync(path.join(dir, name))).render().asPng());
}
