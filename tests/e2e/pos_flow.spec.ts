import { test, expect } from '@playwright/test';

test.describe('Odoo 20 POS & SaaS Ecosystem E2E Tests', () => {

  test('1. Otentikasi Web Login Odoo 20', async ({ page }) => {
    await page.goto('/web/login');
    
    const loginInput = page.locator('input[name="login"]');
    await loginInput.waitFor({ state: 'attached' });
    
    // Pastikan form login aktif dan terlihat
    const isVisible = await loginInput.isVisible();
    if (!isVisible) {
      await page.evaluate(() => {
        document.querySelectorAll('.oe_login_form.d-none').forEach(el => el.classList.remove('d-none'));
      });
    }

    await loginInput.fill('e2e_tester');
    await page.locator('input[name="password"]').fill('e2e_password_pos20');
    await page.locator('button[type="submit"]:has-text("Log in")').click();

    // Verifikasi URL Odoo 20
    await page.waitForURL(/\/odoo/, { timeout: 15000 });
    await expect(page).toHaveTitle(/Odoo/i);
    
    // Verifikasi navbar web client Odoo 20
    const navbar = page.locator('nav, .o_main_navbar, .o_navbar');
    await expect(navbar.first()).toBeVisible({ timeout: 10000 });
  });

  test('2. Navigasi ke Dashboard Point of Sale', async ({ page }) => {
    await page.goto('/web/login');
    const loginInput = page.locator('input[name="login"]');
    await loginInput.waitFor({ state: 'attached' });
    if (!(await loginInput.isVisible())) {
      await page.evaluate(() => {
        document.querySelectorAll('.oe_login_form.d-none').forEach(el => el.classList.remove('d-none'));
      });
    }
    await loginInput.fill('e2e_tester');
    await page.locator('input[name="password"]').fill('e2e_password_pos20');
    await page.locator('button[type="submit"]:has-text("Log in")').click();
    await page.waitForURL(/\/odoo/, { timeout: 15000 });

    // Buka kanban Point of Sale
    await page.goto('/odoo/action-point_of_sale.action_pos_config_kanban');
    await page.waitForTimeout(2000);

    // Verifikasi toko Bakery Shop tampil
    const bakeryShop = page.locator('text=Bakery Shop');
    await expect(bakeryShop.first()).toBeVisible({ timeout: 15000 });
  });

  test('3. Antarmuka Kasir POS UI & License Banner OWL 3', async ({ page }) => {
    await page.goto('/web/login');
    const loginInput = page.locator('input[name="login"]');
    await loginInput.waitFor({ state: 'attached' });
    if (!(await loginInput.isVisible())) {
      await page.evaluate(() => {
        document.querySelectorAll('.oe_login_form.d-none').forEach(el => el.classList.remove('d-none'));
      });
    }
    await loginInput.fill('e2e_tester');
    await page.locator('input[name="password"]').fill('e2e_password_pos20');
    await page.locator('button[type="submit"]:has-text("Log in")').click();
    await page.waitForURL(/\/odoo/, { timeout: 15000 });

    // Buka UI POS Bakery Shop
    await page.goto('/pos/ui/1');

    // Tunggu antarmuka POS dimuat
    const posApp = page.locator('.point-of-sale, .pos, .pos-topheader');
    await expect(posApp.first()).toBeVisible({ timeout: 25000 });

    // 1. Validasi Keberadaan License Banner OWL 3 (pos_saas_license)
    const licenseBanner = page.locator('.pos-saas-license-banner');
    await expect(licenseBanner).toBeVisible({ timeout: 10000 });
    // Verifikasi teks toleransi grace period
    await expect(licenseBanner).toContainText(/masa tenggang/i);

    // 2. Klik tombol "Open Register" untuk membuka layar kasir
    const openRegisterBtn = page.locator('button:has-text("Open Register")');
    if (await openRegisterBtn.isVisible()) {
      await openRegisterBtn.click();
      await page.waitForTimeout(1000);
    }

    // 3. Verifikasi elemen katalog produk atau order screen
    const registerScreen = page.locator('.product-screen, .products-widget, .order-container, button:has-text("Register")');
    await expect(registerScreen.first()).toBeVisible({ timeout: 10000 });

    // Ambil bukti tangkapan layar tampilan POS UI & License Banner
    await page.screenshot({ path: 'screenshots/e2e-pos-ui-license-banner.png' });
  });

  test('4. Menu SaaS License Server & Records', async ({ page }) => {
    await page.goto('/web/login');
    const loginInput = page.locator('input[name="login"]');
    await loginInput.waitFor({ state: 'attached' });
    if (!(await loginInput.isVisible())) {
      await page.evaluate(() => {
        document.querySelectorAll('.oe_login_form.d-none').forEach(el => el.classList.remove('d-none'));
      });
    }
    await loginInput.fill('e2e_tester');
    await page.locator('input[name="password"]').fill('e2e_password_pos20');
    await page.locator('button[type="submit"]:has-text("Log in")').click();
    await page.waitForURL(/\/odoo/, { timeout: 15000 });

    // Akses view License Records
    await page.goto('/odoo/action-saas_license_server.action_saas_license_record');
    await page.waitForTimeout(2000);

    // Verifikasi tampilan list records atau control panel
    const listRecords = page.locator('.o_list_view, .o_control_panel, .o_breadcrumb');
    await expect(listRecords.first()).toBeVisible({ timeout: 15000 });
    
    // Verifikasi record lisensi diva resto muncul di daftar
    const merchantCell = page.locator('td:has-text("diva resto")');
    await expect(merchantCell.first()).toBeVisible({ timeout: 10000 });
  });

  test('5. Menu SaaS Access Management Rules', async ({ page }) => {
    await page.goto('/web/login');
    const loginInput = page.locator('input[name="login"]');
    await loginInput.waitFor({ state: 'attached' });
    if (!(await loginInput.isVisible())) {
      await page.evaluate(() => {
        document.querySelectorAll('.oe_login_form.d-none').forEach(el => el.classList.remove('d-none'));
      });
    }
    await loginInput.fill('e2e_tester');
    await page.locator('input[name="password"]').fill('e2e_password_pos20');
    await page.locator('button[type="submit"]:has-text("Log in")').click();
    await page.waitForURL(/\/odoo/, { timeout: 15000 });

    // Akses view Access Rules
    await page.goto('/odoo/action-saas_access_management.action_saas_access_rule');
    await page.waitForTimeout(2000);

    // Verifikasi view control panel dan list rules
    const accessRulesView = page.locator('.o_list_view, .o_control_panel, .o_breadcrumb');
    await expect(accessRulesView.first()).toBeVisible({ timeout: 15000 });
  });

});
