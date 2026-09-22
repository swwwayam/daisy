// Positional replacement of fake-stat cards in App.tsx — encoding-proof.
const fs = require("fs");
const p = "src/App.tsx";
let c = fs.readFileSync(p, "utf8");

const startIdx = c.indexOf('<FloatCard className="fc-1"');
if (startIdx === -1) { console.log("NOT FOUND"); process.exit(0); }

const fc4Pos = c.indexOf("fc-4", startIdx);
const closeTag = "</FloatCard>";
const afterFc4 = c.indexOf(closeTag, fc4Pos);
const endIdx = afterFc4 + closeTag.length;

const replacement = `      <div className="hero-stat reveal-3d">
        <span className="stat-muted">One conversation drives the full pipeline</span>
        <span className="stat-divider" />
        <span className="stat-muted">Zero setup · Full transparency</span>
        <span className="stat-divider" />
        <span className="stat-muted">Open pipeline you can audit end to end</span>
      </div>`;

c = c.slice(0, startIdx) + replacement + c.slice(endIdx);
fs.writeFileSync(p, c, "utf8");
console.log("REPLACED OK. New length:", c.length);
