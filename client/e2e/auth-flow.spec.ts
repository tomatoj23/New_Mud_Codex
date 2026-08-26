import { randomUUID } from "node:crypto";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const nativeInput = (page: Page, testId: string) =>
  page.getByTestId(testId).locator("input");

async function registerAndLogin(page: Page, username: string, password: string) {
  await page.goto("/");
  await nativeInput(page, "username").fill(username);
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("recovery-code")).toBeVisible();
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("session-panel")).toBeVisible();
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
  await nativeInput(page, "username").fill(username);
  await nativeInput(page, "password").fill(password);
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("recovery-code")).toBeVisible();
  await expect(page.getByTestId("announcement")).toContainText(
    "请妥善保存恢复码，然后使用独立登录",
  );
  await expect(page.getByRole("heading", { name: "登录江湖" })).toBeVisible();
  await expect(page.getByTestId("session-panel")).toHaveCount(0);

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

  const registrationResponse = page.waitForResponse("**/api/v1/auth/register");
  await registerAndLogin(page, username, password);
  const recoveryCode = (await (await registrationResponse).json()).recovery_code as string;
  const refreshResponse = page.waitForResponse("**/api/v1/auth/refresh");
  await page.getByTestId("refresh").click();
  const accessToken = (await (await refreshResponse).json()).access_token as string;
  await expect(page.getByTestId("announcement")).toContainText("会话已安全刷新");

  const persistedWhileAuthenticated = JSON.stringify(await browserPersistence(page));
  expect(persistedWhileAuthenticated).not.toContain(accessToken);
  expect(persistedWhileAuthenticated).not.toContain(recoveryCode);
  expect(persistedWhileAuthenticated).not.toMatch(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\./);

  await page.getByTestId("logout").click();
  await expect(page.getByTestId("session-panel")).toHaveCount(0);
  const persistedAfterLogout = JSON.stringify(await browserPersistence(page));
  expect(persistedAfterLogout).not.toContain(accessToken);
  expect(persistedAfterLogout).not.toContain(recoveryCode);
  expect(persistedAfterLogout).not.toContain("access_token");
  expect(JSON.stringify(consoleMessages)).not.toContain(accessToken);
  expect(JSON.stringify(consoleMessages)).not.toContain(recoveryCode);

  const refreshCookie = (await context.cookies()).find(
    (cookie) => cookie.name === "new_mud_refresh",
  );
  expect(refreshCookie).toBeUndefined();
});
