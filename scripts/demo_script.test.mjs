// Offline checks for the demo script (task 4.9). Run: node --test scripts/
import assert from "node:assert/strict";
import { test } from "node:test";
import { ANSWERS, CAPTIONS, findSensitive } from "./demo_script.mjs";

test("captions and answers have no sensitive data", () => {
  for (const text of [...Object.values(CAPTIONS), ...ANSWERS]) {
    assert.deepEqual(findSensitive(text), [], text);
  }
});

test("detector catches each sensitive pattern", () => {
  const cases = {
    url: "veja https://abc.execute-api.us-east-1.amazonaws.com/prod",
    email: "fale com alguem@exemplo.com",
    "aws-account": "conta 123456789012",
    arn: "arn:aws:iam::role/x",
    uuid: "id 3f2b8c1e-9a4d-4e2f-8b1a-0c9d8e7f6a5b",
  };
  for (const [name, text] of Object.entries(cases)) {
    assert.ok(findSensitive(text).includes(name), name);
  }
});

test("captions are short sentences", () => {
  for (const [key, text] of Object.entries(CAPTIONS)) {
    if (key === "stack") continue; // closing card, shown alone
    assert.ok(text.length <= 90, `${key}: ${text.length}`);
  }
});

test("answers are short", () => {
  for (const text of ANSWERS) assert.ok(text.length <= 220, text);
});
