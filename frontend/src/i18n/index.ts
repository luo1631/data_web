import zh from "./zh.json";
import en from "./en.json";

const messages: Record<string, Record<string, string>> = { zh, en };

export function t(key: string, lang: string = "zh", vars?: Record<string, string | number>): string {
  const keys = key.split(".");
  let val: any = messages[lang] || messages.zh;
  for (const k of keys) {
    val = val?.[k];
  }
  let text = typeof val === "string" ? val : key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}
