// Build the submission .docx in the Apart sprint template's look, from paper/submission.md.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  WidthType, BorderStyle, ShadingType, LevelFormat, FootnoteReferenceRun, ExternalHyperlink,
} = require("docx");

const SRC = "/home/claude/collusion_hackathon/paper/submission.md";
const BASE = "/home/claude/collusion_hackathon/paper";
const OUT = process.argv[2];
const FONT = "Old Standard TT";
const BODY = 21;              // half-points: 10.5pt
const CONTENT_W = 9360;       // 6.5in in DXA (letter, 1in margins)

const md = fs.readFileSync(SRC, "utf8").split("\n");

// ---------- inline markup: **bold**, *italic*, `code`
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size: BODY, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, size: BODY, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Courier New", size: BODY - 2, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, font: FONT, size: BODY, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: BODY, ...base }));
  return out;
}
const para = (text, opts = {}) => new Paragraph({ children: runs(text, opts.run || {}), spacing: { after: 120, line: 276 }, ...opts.p });

function heading(text, level) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, font: FONT, size: level === 2 ? 28 : 23 })],
    spacing: { before: level === 2 ? 320 : 200, after: 120 },
    keepNext: true,
  });
}

// ---------- tables
const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
function table(lines) {
  const rows = lines.filter(l => !/^\|\s*-/.test(l)).map(l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
  const n = rows[0].length;
  const first = n >= 5 ? 1500 : 2200;
  const rest = Math.floor((CONTENT_W - first) / (n - 1));
  const widths = [first, ...Array(n - 1).fill(rest)];
  widths[n - 1] = CONTENT_W - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0, cantSplit: true,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders: { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder },
        shading: i === 0 ? { type: ShadingType.CLEAR, fill: "EEEEEE", color: "auto" } : undefined,
        margins: { top: 60, bottom: 60, left: 80, right: 80 },
        children: [new Paragraph({ children: runs(c, { size: 18, bold: i === 0 ? true : undefined }) })],
      })),
    })),
  });
}

// ---------- title block (matches the template)
const children = [];
const title = md[0].replace(/^#\s*/, "");
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  border: { top: { style: BorderStyle.SINGLE, size: 24, color: "000000", space: 18 },
            bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 18 } },
  spacing: { before: 240, after: 360 },
  children: [new TextRun({ text: title.toUpperCase(), bold: true, font: FONT, size: 30 }), new FootnoteReferenceRun(1)],
}));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 }, children: [new TextRun({ text: "[Author name]", font: FONT, size: BODY })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: "[Affiliation]", font: FONT, size: BODY })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 }, children: [new TextRun({ text: "With", bold: true, font: FONT, size: BODY })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: "Apart Research", font: FONT, size: BODY })] }));

// ---------- body
let i = md.findIndex(l => l.startsWith("## Abstract"));
let listCounter = 0;
while (i < md.length) {
  const l = md[i];
  if (l.startsWith("## Abstract")) {
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({ text: "Abstract", bold: true, font: FONT, size: 26 })] }));
    i++; const buf = [];
    while (i < md.length && !md[i].startsWith("## ")) { if (md[i].trim()) buf.push(md[i].trim()); i++; }
    children.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 1080, right: 1080 }, spacing: { after: 240, line: 276 },
      children: runs(buf.join(" "), { italics: true }) }));
    continue;
  }
  if (l.startsWith("### ")) { children.push(heading(l.slice(4), 3)); i++; continue; }
  if (l.startsWith("## ")) { children.push(heading(l.slice(3), 2)); i++; continue; }
  if (l.startsWith("|")) {
    const tl = []; while (i < md.length && md[i].startsWith("|")) tl.push(md[i++]);
    children.push(table(tl)); children.push(new Paragraph({ spacing: { after: 120 }, children: [] })); continue;
  }
  const img = l.match(/^!\[.*\]\((.+)\)/);
  if (img) {
    const data = fs.readFileSync(path.join(BASE, img[1]));
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: "png", data, transformation: { width: 600, height: Math.round(600 * data.readUInt32BE(20) / data.readUInt32BE(16)) } })] }));
    i++; continue;
  }
  if (/^\d+\.\s/.test(l) || /^- /.test(l)) {
    const numbered = /^\d+\.\s/.test(l);
    const ref = numbered ? `num${listCounter++}` : "bullets";
    while (i < md.length && (/^\d+\.\s/.test(md[i]) || /^- /.test(md[i]) || /^\s{2,}\S/.test(md[i]))) {
      let item = md[i].replace(/^\d+\.\s|^- /, "").trim(); i++;
      while (i < md.length && /^\s{2,}\S/.test(md[i])) { item += " " + md[i].trim(); i++; }
      children.push(new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 276 }, children: runs(item) }));
    }
    continue;
  }
  if (!l.trim()) { i++; continue; }
  const buf = [];
  while (i < md.length && md[i].trim() && !/^(#|\||!\[|- |\d+\.\s)/.test(md[i])) buf.push(md[i++].trim());
  const text = buf.join(" ");
  const caption = /^\*\*(Figure|Table) \d/.test(text);
  children.push(para(text, { run: caption ? { size: 19 } : {}, p: caption ? { spacing: { after: 160, line: 252 } } : {} }));
}

const numConfigs = [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }];
for (let k = 0; k < 20; k++) numConfigs.push({ reference: `num${k}`, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
  alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] });

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: numConfigs },
  footnotes: { 1: { children: [new Paragraph({ children: [
    new TextRun({ text: "Research conducted at the ", font: FONT, size: 16 }),
    new ExternalHyperlink({ link: "https://apartresearch.com",
      children: [new TextRun({ text: "AI Collusion Research Sprint", font: FONT, size: 16, color: "1155CC", underline: {} })] }),
    new TextRun({ text: ", October 2026", font: FONT, size: 16 })] })] } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log("written", OUT); });
