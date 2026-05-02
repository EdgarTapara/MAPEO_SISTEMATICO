from __future__ import annotations

import random
import os
import re
from dataclasses import dataclass, field
from time import sleep


@dataclass(slots=True)
class BrowserManager:
    headless: bool = False
    delay_listado: tuple[float, float] = (4.0, 7.0)
    delay_detalle: tuple[float, float] = (2.0, 5.0)
    timeout_elemento: int = 20
    _driver: object | None = field(default=None, init=False)

    def get_driver(self):
        if self._driver is None:
            import undetected_chromedriver as uc

            self._driver = self._start_chrome(uc)
        return self._driver

    def _build_options(self, uc):
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=es-PE,es")
        if self.headless:
            options.add_argument("--headless=new")
        return options

    def _start_chrome(self, uc):
        configured = os.getenv("RENATI_CHROME_VERSION_MAIN")
        if configured and configured.isdigit():
            return uc.Chrome(options=self._build_options(uc), version_main=int(configured))
        installed = _detect_installed_chrome_major()
        if installed is not None:
            return uc.Chrome(options=self._build_options(uc), version_main=installed)
        try:
            return uc.Chrome(options=self._build_options(uc), version_main=None)
        except Exception as exc:
            detected = _extract_chrome_major_version(str(exc))
            if detected is None:
                raise
            return uc.Chrome(options=self._build_options(uc), version_main=detected)

    def navigate(self, url: str, kind: str = "detalle"):
        driver = self.get_driver()
        driver.get(url)
        delay_range = self.delay_listado if kind == "listado" else self.delay_detalle
        sleep(random.uniform(*delay_range))
        self.wait_if_antibot(driver)
        self.close_common_banners(driver)
        return driver

    def wait_if_antibot(self, driver, max_wait_seconds: int = 90) -> None:
        elapsed = 0
        while elapsed < max_wait_seconds:
            html = (driver.page_source or "").lower()
            title = (getattr(driver, "title", "") or "").lower()
            if "anubis_challenge" not in html and "not a bot" not in title and "making sure" not in html:
                return
            sleep(3)
            elapsed += 3

    def close_common_banners(self, driver) -> None:
        try:
            from selenium.webdriver.common.by import By

            selectors = [
                "//button[contains(translate(., 'ACEPTO', 'acepto'), 'acepto')]",
                "//button[contains(translate(., 'ACEPTAR', 'aceptar'), 'aceptar')]",
            ]
            for selector in selectors:
                try:
                    button = driver.find_element(By.XPATH, selector)
                    button.click()
                    break
                except Exception:
                    continue
        except Exception:
            return

    def close(self) -> None:
        if self._driver is None:
            return
        driver = self._driver
        try:
            driver.quit()
        except Exception:
            pass
        try:
            driver.service = None
        except Exception:
            pass
        try:
            driver.__class__.__del__ = lambda self: None
        except Exception:
            pass
        self._driver = None

    def __enter__(self) -> "BrowserManager":
        self.get_driver()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False


def _extract_chrome_major_version(message: str) -> int | None:
    match = re.search(r"Current browser version is\s+(\d+)", message)
    if match:
        return int(match.group(1))
    return None


def _detect_installed_chrome_major() -> int | None:
    try:
        import winreg

        keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Google\Chrome\BLBeacon"),
        ]
        for root, path in keys:
            try:
                with winreg.OpenKey(root, path) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
                match = re.match(r"(\d+)", str(version))
                if match:
                    return int(match.group(1))
            except OSError:
                continue
    except Exception:
        return None
    return None
