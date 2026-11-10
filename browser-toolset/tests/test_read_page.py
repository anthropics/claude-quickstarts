import ast
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
NODE_READ_PAGE_TEST = r"""
const vm = require("node:vm");
const [pythonScript, typescriptDeclaration] = JSON.parse(require("node:fs").readFileSync(0, "utf8"));

function readTypescriptScript() {
  return vm.runInNewContext(`${typescriptDeclaration}; READ_PAGE`, {});
}

function runReadPage(script) {
  function element(type, value, attributes = {}, style = {}) {
    return {
      tagName: "INPUT",
      type,
      value,
      style,
      innerText: "",
      placeholder: attributes.placeholder || "",
      getAttribute(name) {
        return attributes[name] ?? null;
      },
      getBoundingClientRect() {
        return { width: 10, height: 10 };
      },
    };
  }

  const password = element("password", "FAKE_PASSWORD_123", { "aria-label": "Password" });
  const unlabelledPassword = element("password", "ANOTHER_FAKE_PASSWORD");
  const cssMaskedPin = element("tel", "FAKE_PIN_4567", { placeholder: "PIN" }, { webkitTextSecurity: "disc" });
  const otpCode = element("text", "FAKE_OTP_890123", { autocomplete: "one-time-code", placeholder: "Verification code" });
  const cardCvc = element("text", "FAKE_CVC_999", { autocomplete: "cc-csc", placeholder: "CVC" });
  const text = element("text", "visible-user");
  const getComputedStyle = (el) => ({ webkitTextSecurity: el.style?.webkitTextSecurity || "none" });
  const window = { getComputedStyle };
  const document = {
    querySelectorAll: () => [password, unlabelledPassword, cssMaskedPin, otpCode, cardCvc, text],
  };
  return vm.runInNewContext(script, { window, document, getComputedStyle });
}

for (const script of [pythonScript, readTypescriptScript()]) {
  const output = runReadPage(script);
  for (const secret of [
    "FAKE_PASSWORD_123",
    "ANOTHER_FAKE_PASSWORD",
    "FAKE_PIN_4567",
    "FAKE_OTP_890123",
    "FAKE_CVC_999",
  ]) {
    if (output.includes(secret)) {
      throw new Error(`secret value leaked (${secret}): ${output}`);
    }
  }
  if (!output.includes('textbox "Password"')) {
    throw new Error(`password control lost its accessible label: ${output}`);
  }
  if (!output.includes('textbox "PIN"') || !output.includes('textbox "Verification code"') || !output.includes('textbox "CVC"')) {
    throw new Error(`masked control lost its placeholder fallback: ${output}`);
  }
  if (!output.includes('textbox "visible-user"')) {
    throw new Error(`ordinary input value disappeared: ${output}`);
  }
}
"""


def read_page_script(path: Path) -> str:
    text = path.read_text()
    if path.suffix == ".py":
        module = ast.parse(text)
        return next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(getattr(target, "id", None) == "READ_PAGE" for target in node.targets)
        )

    prefix = "const READ_PAGE = `"
    start = text.index(prefix)
    close = re.search(r"(?<!\\)`", text[start + len(prefix) :])
    if close is None:
        raise ValueError(f"unterminated READ_PAGE template literal in {path}")
    end = start + len(prefix) + close.end()
    return text[start:end]


@unittest.skipUnless(shutil.which("node"), "node is required to execute READ_PAGE scripts")
class ReadPageTest(unittest.TestCase):
    def test_password_values_are_not_exposed(self) -> None:
        scripts = [
            read_page_script(ROOT / "python/cdp_browser.py"),
            read_page_script(ROOT / "typescript/cdp-browser.ts"),
        ]
        completed = subprocess.run(
            ["node", "-e", NODE_READ_PAGE_TEST],
            input=json.dumps([scripts[0], scripts[1]]),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
