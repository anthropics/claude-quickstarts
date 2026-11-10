import ast
import json
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
  function element(type, value, attributes = {}) {
    return {
      tagName: "INPUT",
      type,
      value,
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
  const text = element("text", "visible-user");
  const window = {};
  const document = { querySelectorAll: () => [password, unlabelledPassword, text] };
  return vm.runInNewContext(script, { window, document });
}

for (const script of [pythonScript, readTypescriptScript()]) {
  const output = runReadPage(script);
  if (output.includes("FAKE_PASSWORD_123") || output.includes("ANOTHER_FAKE_PASSWORD")) {
    throw new Error(`password value leaked: ${output}`);
  }
  if (!output.includes('textbox "Password"')) {
    throw new Error(`password control lost its accessible label: ${output}`);
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

    start = text.index("const READ_PAGE = `")
    end = text.index("`;\n\n// The viewport", start) + 1
    return text[start:end]


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
