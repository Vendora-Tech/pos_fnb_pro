import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

const VALID_TOKEN = 'eyJhbGciOiJFZERTQSIsInR5cCI6IlNBQVMtTElDIiwia2lkIjoicHJvZEAyMDI2In0.eyJsaWQiOiJMSUMtMjAyNi0wMDc0IiwibWNoIjoiZGl2YSByZXN0byIsInR5cCI6InN1YnNjcmlwdGlvbiIsImRiX3V1aWQiOiI0YzY1MGRhMy1iZWZjLTExZjEtODUzNC05NzFjNmUzY2JkMDAiLCJtYXhfcmVnIjoxLCJmcm9tIjoiMjAyNi0xMS0wNyIsInVudGlsIjoiMjAyNi0xMS0wOCIsImdyYWNlIjo3fQ.XECCsO2QclfXnWFwEaIVJP5ieuGGrgDo2EWo7Fd8ONe-HCmx15VHYWGx5lS8IV7TYgvwmfnQ2QLTxNlysVlCDQ';

function setBackendLicenseToken(token: string) {
  try {
    const cmd = `docker exec odoo20-pos-odoo20-1 python3 -c "import odoo; from odoo.modules.registry import Registry; from odoo import api; odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'pos', '--db_host=db', '--db_user=odoo20_user', '--db_password=BJLAQ4syhvqbwUCKsBFgXi6RZT3mieks']); reg = Registry('pos'); cr = reg.cursor(); env = api.Environment(cr, odoo.SUPERUSER_ID, {}); lic = env['pos.saas.license'].search([], limit=1); lic.write({'raw_token': '${token}'}); session = env['pos.session'].browse(1); session._compute_license_banner_data(); cr.commit(); cr.close()"`;
    execSync(cmd, { timeout: 15000 });
  } catch (err) {
    console.warn('Backend license helper warning:', err);
  }
}

test.describe('Odoo 20 POS & SaaS Ecosystem E2E Tests', () => {
  // Jalankan berurutan agar mutasi state lisensi di test 7 tidak balapan dengan kasir di test 6
  test.describe.configure({ mode: 'serial' });

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
    await page.waitForTimeout(3000);

    // Verifikasi LicenseBanner OWL 3 ter-render di atas navbar POS
    const licenseBanner = page.locator('.pos-saas-license-banner, .alert');
    await expect(licenseBanner.first()).toBeVisible({ timeout: 10000 });

    // Verifikasi layar kerja kasir
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

  test('6. Skenario Transaksi Kasir POS (Checkout Flow E2E)', async ({ page }) => {
    test.setTimeout(45000);
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
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

    // Buka UI kasir POS Bakery Shop
    await page.goto('/pos/ui/1');
    await page.waitForTimeout(3000);

    // Buka register jika berada pada landing screen / dialog opening control
    const openRegBtn = page.getByRole('button', { name: 'Open Register' });
    while (await openRegBtn.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await openRegBtn.first().click();
      await page.waitForTimeout(2000);
    }

    // 1. Pilih produk yang tersedia di layar kasir (Roti Sobek Cokelat Keju)
    const prodCard = page.getByRole('button', { name: 'Roti Sobek Cokelat Keju' }).first();
    await prodCard.waitFor({ state: 'visible', timeout: 15000 });
    await prodCard.click();
    await page.waitForTimeout(1000);

    // 2. Klik tombol Payment di Action Pad
    const payBtn = page.getByRole('button', { name: 'Payment' }).first();
    await expect(payBtn).toBeVisible({ timeout: 15000 });
    await page.evaluate(() => {
      const btn = document.querySelector('button.pay-order-button');
      if (btn) btn.click();
    });
    await page.waitForTimeout(2000);

    // 3. Pada layar Payment, klik tombol validasi pembayaran (Cash / Bank)
    const validateBtn = page.locator('button.validation-button, .button.next').first();
    await expect(validateBtn).toBeVisible({ timeout: 15000 });
    await validateBtn.click();
    await page.waitForTimeout(3000);

    // 4. Verifikasi layar Receipt / FeedbackScreen terbentuk
    const isFeedbackScreen = await page.locator('.feedback-screen').isVisible();
    expect(isFeedbackScreen).toBeTruthy();

    // Tangkap bukti screenshot transaksi berhasil
    await page.screenshot({ path: 'screenshots/e2e-pos-checkout-success.png' });

    // 5. Klik Continue untuk menyelesaikan transaksi
    const btnNext = page.locator('button:has-text("Continue")');
    if (await btnNext.isVisible()) {
      await btnNext.click();
      await page.waitForTimeout(1000);
    }
  });

  test('7. Pengujian Hard-Block Lisensi Expired / Read-Only POS Mode', async ({ page }) => {
    try {
      // 1. Simulasikan token lisensi expired di backend
      setBackendLicenseToken('expired.token.signature');

      // 2. Buka UI kasir
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

      await page.goto('/pos/ui/1');
      await page.waitForTimeout(3000);

      // 3. Verifikasi banner lisensi memuat pesan kunci transaksi
      const expiredBanner = page.locator('.pos-saas-license-banner, .alert');
      await expect(expiredBanner.first()).toBeVisible({ timeout: 10000 });
      const bannerText = await expiredBanner.first().innerText();
      expect(bannerText).toContain('Masa berlaku lisensi telah habis atau tidak valid');

      // 4. Buka register jika berada pada landing screen / dialog opening control
      const openRegBtn = page.getByRole('button', { name: 'Open Register' });
      while (await openRegBtn.first().isVisible({ timeout: 3000 }).catch(() => false)) {
        await openRegBtn.first().click();
        await page.waitForTimeout(2000);
      }

      // 5. Masukkan produk ke keranjang
      const prodCard = page.getByRole('button', { name: 'Roti Sobek Cokelat Keju' }).first();
      await prodCard.waitFor({ state: 'visible', timeout: 15000 });
      await prodCard.click();
      await page.waitForTimeout(1000);

      // Jika muncul dialog add-ons, pilih opsi dan klik Add
      const configDialog = page.locator('div[role="dialog"]');
      if (await configDialog.isVisible({ timeout: 2500 }).catch(() => false)) {
        const optBtn = configDialog.locator('button.btn-light, button.btn-outline-primary, button:has-text("Roti Utuh"), .attribute-value').first();
        if (await optBtn.isVisible()) {
          await optBtn.click();
          await page.waitForTimeout(300);
        }
        const addBtn = configDialog.locator('footer button:has-text("Add"), button:has-text("Add")').first();
        if (await addBtn.isVisible()) {
          await addBtn.click();
          await page.waitForTimeout(1000);
        }
      }

      // 6. Verifikasi tombol Payment berstatus DISABLED atau TERKUNCI (pointer-events: none / disabled)
      const payBtn = page.getByRole('button', { name: 'Payment' }).first();
      await expect(payBtn).toBeVisible({ timeout: 15000 });
      const isDisabled = await payBtn.isDisabled();
      const pointerEvents = await payBtn.evaluate((el) => window.getComputedStyle(el).pointerEvents);
      expect(isDisabled || pointerEvents === 'none').toBeTruthy();

      // Tangkap bukti screenshot mode read-only hard-block
      await page.screenshot({ path: 'screenshots/e2e-pos-hardblock-expired.png' });

    } finally {
      // 7. Selalu pulihkan token lisensi valid kembali ke database
      setBackendLicenseToken(VALID_TOKEN);
    }
  });

});
