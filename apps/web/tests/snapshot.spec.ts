import { expect, test } from "@playwright/test";

test("creates a logical snapshot through the existing researcher screen", async ({ page }) => {
  await page.route("**/v1/snapshots/logical", async (route) => {
    expect(route.request().method()).toBe("POST");
    expect(await route.request().postDataJSON()).toEqual({ project_id: "TCGA-LUAD" });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ snapshot_id: "snapshot-browser-smoke" }),
    });
  });

  await page.goto("/projects/TCGA-LUAD");
  await expect(page.getByRole("heading", { name: "TCGA-LUAD" })).toBeVisible();
  await expect(page.getByText("Research use only. Not for diagnosis or treatment decisions.")).toBeVisible();
  await page.getByRole("button", { name: "Create logical snapshot" }).click();
  await expect(page.getByText("Snapshot created:")).toContainText("snapshot-browser-smoke");
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
});
