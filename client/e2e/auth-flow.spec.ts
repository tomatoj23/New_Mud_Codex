import { randomUUID } from "node:crypto";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { deliverRegistrationCode } from "./verification-test-support";

const nativeInput = (page: Page, testId: string) =>
  page.getByTestId(testId).locator("input");

async function registerAndLogin(page: Page, username: string, password: string) {
  const email = `${username}@example.com`;
  await page.goto("/");
  await nativeInput(page, "email").fill(email);
  await page.getByTestId("request-verification").click();
  await expect(page.getByTestId("verification-hint")).toBeVisible();
  const code = await deliverRegistrationCode(email);
  await nativeInput(page, "verification-code").fill(code);
  await nativeInput(page, "username").fill(username);
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("announcement")).toContainText("注册成功，请登录");
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("session-panel")).toBeVisible();
  return { code, email };
}

async function login(page: Page, username: string, password: string) {
  await page.goto("/");
  await page.getByTestId("login-tab").click();
  await nativeInput(page, "username").fill(username);
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("session-panel")).toBeVisible();
}

async function browserPersistence(page: Page) {
  return page.evaluate(async () => {
    const indexedDb: Record<string, unknown> = {};
    for (const databaseInfo of await indexedDB.databases()) {
      if (!databaseInfo.name) continue;
      indexedDb[databaseInfo.name] = await new Promise((resolve, reject) => {
        const request = indexedDB.open(databaseInfo.name as string);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
          const database = request.result;
          const stores = Array.from(database.objectStoreNames);
          if (stores.length === 0) {
            database.close();
            resolve({});
            return;
          }
          const transaction = database.transaction(stores, "readonly");
          const result: Record<string, unknown> = {};
          for (const storeName of stores) {
            const getAll = transaction.objectStore(storeName).getAll();
            getAll.onsuccess = () => {
              result[storeName] = getAll.result;
            };
          }
          transaction.onerror = () => reject(transaction.error);
          transaction.oncomplete = () => {
            database.close();
            resolve(result);
          };
        };
      });
    }

    const cacheStorage: Record<string, string[]> = {};
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      cacheStorage[cacheName] = await Promise.all(
        (await cache.keys()).map(async (request) => {
          const response = await cache.match(request);
          return `${request.url}\n${response ? await response.text() : ""}`;
        }),
      );
    }

    return {
      localStorage: { ...localStorage },
      sessionStorage: { ...sessionStorage },
      indexedDb,
      cacheStorage,
    };
  });
}

test("registration stays separate, then login refresh and logout complete", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name.replace(/\W/g, "_").slice(0, 10);
  const username = `e1_${project}_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
  const password = "safe-e2e-passphrase-42";

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "创建江湖账号" })).toBeVisible();
  const email = `${username}@example.com`;
  await page.route("**/api/v1/auth/registration-verification/request", async (route) => {
    const response = await route.fetch();
    const payload = (await response.json()) as { status: string; retry_after: number };
    expect(payload).toEqual({ status: "accepted", retry_after: 60 });
    await route.fulfill({ response, json: { ...payload, retry_after: 1 } });
  }, { times: 1 });
  await nativeInput(page, "email").fill(email);
  await page.getByTestId("request-verification").click();
  await expect(page.getByTestId("verification-hint")).toBeVisible();
  const verificationButton = page.getByTestId("request-verification");
  await expect(verificationButton).toHaveAttribute("disabled", "true");
  await expect(verificationButton).toContainText("1 秒后可重发");
  const code = await deliverRegistrationCode(email);

  await expect(verificationButton).toContainText("重新发送验证码");
  await page.route("**/api/v1/auth/registration-verification/request", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "accepted", retry_after: 60 }),
    });
  }, { times: 1 });
  await verificationButton.click();
  await expect(verificationButton).toContainText("60 秒后可重发");

  await nativeInput(page, "verification-code").fill(code);
  await nativeInput(page, "username").fill(username);
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("announcement")).toContainText("注册成功，请登录");
  await expect(page.getByRole("heading", { name: "登录江湖" })).toBeVisible();
  await expect(page.getByTestId("session-panel")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("独立登录");
  await expect(page.locator("body")).not.toContainText("恢复码");

  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("session-panel")).toBeVisible();
  await expect(page.getByTestId("announcement")).toContainText("登录成功");

  await page.getByTestId("refresh").click();
  await expect(page.getByTestId("announcement")).toContainText("会话已安全刷新");

  await page.getByTestId("logout").click();
  await expect(page.getByTestId("session-panel")).toHaveCount(0);
  await expect(page.getByTestId("announcement")).toContainText("已安全退出");
  await expect(page.getByTestId("submit")).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
});

test("stable machine errors become explicit user-facing states", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("login-tab").click();
  await nativeInput(page, "username").fill("missing_player");
  await nativeInput(page, "password").fill("incorrect-password-42");
  await page.getByTestId("submit").click();

  const error = page.getByTestId("error");
  await expect(error).toContainText("账号名或密码不正确");
  await expect(error).toContainText("AUTH_CREDENTIALS_INVALID");
});

test("minimum 360 by 640 CSS viewport remains a no-overflow guard", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "single minimum-layout guard");
  await page.setViewportSize({ width: 360, height: 640 });
  await page.goto("/");
  await expect(page.getByTestId("submit")).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.scrollWidth).toBe(dimensions.clientWidth);
});

test("a committed refresh with a lost response resumes after reload with the same key", async ({
  context,
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "single persistence recovery path");
  const username = `e1_reload_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
  const password = "safe-e2e-passphrase-42";
  await registerAndLogin(page, username, password);

  const idempotencyKeys: string[] = [];
  const predecessorCookie = (await context.cookies()).find(
    (cookie) => cookie.name === "new_mud_refresh",
  );
  expect(predecessorCookie).toBeDefined();
  let dropFirstResponse = true;
  await context.route("**/api/v1/auth/refresh", async (route) => {
    idempotencyKeys.push(route.request().headers()["idempotency-key"] ?? "");
    if (dropFirstResponse) {
      dropFirstResponse = false;
      const committed = await route.fetch();
      expect(committed.status()).toBe(200);
      await context.addCookies([predecessorCookie!]);
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  await page.getByTestId("refresh").click();
  await expect(page.getByTestId("error")).toContainText("AUTH_REQUEST_FAILED");
  await page.reload();

  await expect(page.getByTestId("session-panel")).toBeVisible();
  await expect(page.getByTestId("announcement")).toContainText("会话刷新已安全重试");
  expect(idempotencyKeys).toHaveLength(2);
  expect(idempotencyKeys[1]).toBe(idempotencyKeys[0]);
});

test("two tabs refresh one shared cookie with one logical request", async ({
  context,
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "single multi-tab coordination path");
  const username = `e1_tabs_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
  const password = "safe-e2e-passphrase-42";
  await registerAndLogin(page, username, password);
  const follower = await context.newPage();
  await login(follower, username, password);

  const idempotencyKeys: string[] = [];
  await context.route("**/api/v1/auth/refresh", async (route) => {
    idempotencyKeys.push(route.request().headers()["idempotency-key"] ?? "");
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.continue();
  });

  await Promise.all([
    page.getByTestId("refresh").click(),
    follower.getByTestId("refresh").click(),
  ]);
  await expect(page.getByTestId("announcement")).toContainText("会话已安全刷新");
  await expect(follower.getByTestId("announcement")).toContainText("会话已安全刷新");
  expect(idempotencyKeys).toHaveLength(1);
});

test("authentication secrets never enter browser-persistent storage or console logs", async ({
  context,
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "single browser leakage scan");
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  const username = `e1_storage_${randomUUID().replaceAll("-", "").slice(0, 12)}`;
  const password = "safe-e2e-passphrase-42";

  const { code, email } = await registerAndLogin(page, username, password);
  const refreshResponse = page.waitForResponse("**/api/v1/auth/refresh");
  await page.getByTestId("refresh").click();
  const accessToken = (await (await refreshResponse).json()).access_token as string;
  await expect(page.getByTestId("announcement")).toContainText("会话已安全刷新");

  const persistedWhileAuthenticated = JSON.stringify(await browserPersistence(page));
  expect(persistedWhileAuthenticated).not.toContain(accessToken);
  expect(persistedWhileAuthenticated).not.toContain(password);
  expect(persistedWhileAuthenticated).not.toContain(code);
  expect(persistedWhileAuthenticated).not.toContain(email);
  expect(persistedWhileAuthenticated).not.toMatch(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\./);

  await page.getByTestId("logout").click();
  await expect(page.getByTestId("session-panel")).toHaveCount(0);
  const persistedAfterLogout = JSON.stringify(await browserPersistence(page));
  expect(persistedAfterLogout).not.toContain(accessToken);
  expect(persistedAfterLogout).not.toContain(password);
  expect(persistedAfterLogout).not.toContain(code);
  expect(persistedAfterLogout).not.toContain(email);
  expect(persistedAfterLogout).not.toContain("access_token");
  expect(JSON.stringify(consoleMessages)).not.toContain(accessToken);
  expect(JSON.stringify(consoleMessages)).not.toContain(password);
  expect(JSON.stringify(consoleMessages)).not.toContain(code);
  expect(JSON.stringify(consoleMessages)).not.toContain(email);

  const refreshCookie = (await context.cookies()).find(
    (cookie) => cookie.name === "new_mud_refresh",
  );
  expect(refreshCookie).toBeUndefined();
});
