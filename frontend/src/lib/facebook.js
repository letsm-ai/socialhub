/**
 * Facebook JS SDK loader for WhatsApp Embedded Signup (Meta Tech Provider).
 *
 * Configuration is fetched at runtime from the backend (`GET /api/whatsapp/config`),
 * which exposes `app_id`, `config_id`, and an `enabled` flag.
 * If the backend reports `enabled: false`, the UI falls back to a "Simulate" path.
 */
import { api } from "@/contexts/AuthContext";

let runtimeConfig = null;     // { enabled, app_id, config_id, graph_version }
let configPromise = null;
let loadingPromise = null;

const fetchConfig = async () => {
  if (runtimeConfig) return runtimeConfig;
  if (configPromise) return configPromise;
  configPromise = api.get("/whatsapp/config").then(({ data }) => {
    runtimeConfig = data;
    return data;
  }).catch(() => {
    runtimeConfig = { enabled: false, app_id: "", config_id: "" };
    return runtimeConfig;
  });
  return configPromise;
};

export const isFacebookConfigured = async () => {
  const cfg = await fetchConfig();
  return Boolean(cfg?.enabled);
};

export const loadFacebookSDK = async () => {
  if (typeof window === "undefined") return null;
  const cfg = await fetchConfig();
  if (!cfg.enabled) return null;
  if (window.FB) return window.FB;
  if (loadingPromise) return loadingPromise;

  loadingPromise = new Promise((resolve) => {
    window.fbAsyncInit = function () {
      window.FB.init({
        appId: cfg.app_id,
        cookie: true,
        xfbml: true,
        version: cfg.graph_version || "v20.0",
      });
      resolve(window.FB);
    };
    const id = "facebook-jssdk";
    if (document.getElementById(id)) return;
    const js = document.createElement("script");
    js.id = id;
    js.async = true;
    js.defer = true;
    js.crossOrigin = "anonymous";
    js.src = "https://connect.facebook.net/en_US/sdk.js";
    document.body.appendChild(js);
  });
  return loadingPromise;
};

/**
 * Launch WhatsApp Embedded Signup via FB.login.
 * Resolves with { waba_id, phone_number_id, business_id, code }.
 */
export const launchWhatsAppSignup = async () => {
  const FB = await loadFacebookSDK();
  const cfg = await fetchConfig();
  if (!FB || !cfg.config_id) {
    throw new Error("FB_NOT_CONFIGURED");
  }

  return new Promise((resolve, reject) => {
    let sessionInfo = {};

    const onMessage = (event) => {
      if (event.origin !== "https://www.facebook.com" && event.origin !== "https://web.facebook.com") return;
      try {
        const data = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (data?.type === "WA_EMBEDDED_SIGNUP") {
          if (data.event === "FINISH") {
            sessionInfo = {
              waba_id: data?.data?.waba_id,
              phone_number_id: data?.data?.phone_number_id,
              business_id: data?.data?.business_id,
            };
          } else if (data.event === "CANCEL") {
            window.removeEventListener("message", onMessage);
            reject(new Error("USER_CANCELLED"));
          }
        }
      } catch (_) { /* ignore non-JSON */ }
    };
    window.addEventListener("message", onMessage);

    FB.login(
      (response) => {
        window.removeEventListener("message", onMessage);
        if (!response?.authResponse) {
          return reject(new Error("USER_CANCELLED"));
        }
        const code = response.authResponse.code;
        if (!sessionInfo.waba_id || !sessionInfo.phone_number_id) {
          return reject(new Error("Embedded Signup did not return WABA details. Please retry."));
        }
        resolve({ ...sessionInfo, code });
      },
      {
        config_id: cfg.config_id,
        response_type: "code",
        override_default_response_type: true,
        extras: { feature: "whatsapp_embedded_signup", version: 2 },
      }
    );
  });
};
