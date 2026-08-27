import { execFile } from "node:child_process";
import { mkdir, readdir, readFile, unlink } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const keyMaterial = (value: string) => Buffer.alloc(32, value).toString("base64");

export const emailOutboxDirectory = path.resolve(
  process.cwd(),
  "..",
  "artifacts",
  "reports",
  "playwright-email",
);

export const verificationTestEnvironment: NodeJS.ProcessEnv = {
  NEW_MUD_AUTH_BASELINE_CUTOVER_ENABLED: "1",
  NEW_MUD_VERIFICATION_WORKER_READY: "1",
  NEW_MUD_VERIFICATION_PROVIDER_READY: "1",
  NEW_MUD_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND: "1",
  NEW_MUD_CONTACT_ENCRYPTION_KEYS_JSON: JSON.stringify({ e2e_contact: keyMaterial("c") }),
  NEW_MUD_CONTACT_ENCRYPTION_CURRENT_KEY_ID: "e2e_contact",
  NEW_MUD_CONTACT_LOOKUP_KEYS_JSON: JSON.stringify({ e2e_lookup: keyMaterial("l") }),
  NEW_MUD_CONTACT_LOOKUP_CURRENT_KEY_ID: "e2e_lookup",
  NEW_MUD_VERIFICATION_CODE_PEPPER_KEYS_JSON: JSON.stringify({ e2e_code: keyMaterial("p") }),
  NEW_MUD_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID: "e2e_code",
  NEW_MUD_DELIVERY_PAYLOAD_ENCRYPTION_KEYS_JSON: JSON.stringify({
    e2e_delivery: keyMaterial("d"),
  }),
  NEW_MUD_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID: "e2e_delivery",
  NEW_MUD_EMAIL_BACKEND: "django.core.mail.backends.filebased.EmailBackend",
  NEW_MUD_EMAIL_FILE_PATH: emailOutboxDirectory,
  DEFAULT_FROM_EMAIL: "no-reply@test.invalid",
};

function decodeMessageBody(rawMessage: string): string {
  const transferHeader = "Content-Transfer-Encoding: base64";
  const transferIndex = rawMessage.indexOf(transferHeader);
  if (transferIndex < 0) return rawMessage;
  const encodedSection = rawMessage.slice(transferIndex + transferHeader.length);
  const bodyStart = encodedSection.search(/\r?\n\r?\n/);
  if (bodyStart < 0) return rawMessage;
  const bodyLines = encodedSection
    .slice(bodyStart)
    .split(/\r?\n/)
    .filter((line) => /^[A-Za-z0-9+/=]+$/.test(line));
  return Buffer.from(bodyLines.join(""), "base64").toString("utf8");
}

async function deliverVerificationCode(
  destination: string,
  codePattern: RegExp,
  purposeLabel: string,
): Promise<string> {
  await mkdir(emailOutboxDirectory, { recursive: true });
  const before = new Set(await readdir(emailOutboxDirectory));
  const python =
    process.env.PLAYWRIGHT_PYTHON ??
    (process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");
  await execFileAsync(
    python,
    ["manage.py", "process_verification_deliveries", "--limit", "100"],
    {
      cwd: path.resolve(process.cwd(), ".."),
      env: {
        ...process.env,
        ...verificationTestEnvironment,
        DJANGO_SETTINGS_MODULE: "new_mud.settings.development",
      },
    },
  );
  const created = (await readdir(emailOutboxDirectory)).filter((file) => !before.has(file));
  let deliveredCode: string | null = null;
  for (const file of created) {
    const filePath = path.join(emailOutboxDirectory, file);
    const rawMessage = await readFile(filePath, "utf8");
    await unlink(filePath);
    if (!rawMessage.includes(`To: ${destination}`)) continue;
    const match = decodeMessageBody(rawMessage).match(codePattern);
    if (match) deliveredCode = match[1];
  }
  if (deliveredCode === null) {
    throw new Error(
      `Fake email provider did not receive a ${purposeLabel} code for ${destination}`,
    );
  }
  return deliveredCode;
}

export function deliverRegistrationCode(destination: string): Promise<string> {
  return deliverVerificationCode(destination, /注册验证码是：(\d{6})/u, "registration");
}

export function deliverPasswordResetCode(destination: string): Promise<string> {
  return deliverVerificationCode(destination, /密码重置验证码是：(\d{6})/u, "password reset");
}
