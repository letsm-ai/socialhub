/**
 * Facebook JS SDK loader for WhatsApp Embedded Signup.
 * Reads REACT_APP_FACEBOOK_APP_ID and REACT_APP_WA_CONFIG_ID from env (set them when going live).
 * Until they are set, the loader is a no-op and the UI falls back to a "Simulate" path.
 */
const FB_APP_ID = process.env.REACT_APP_FACEBOOK_APP_ID || "";
const WA_CONFIG_ID = process.env.REACT_APP_WA_CONFIG_ID || "";

let loadingPromise = null;

export const isFacebookConfigured = () => Boolean(FB_APP_ID && WA_CONFIG_ID);

export const loadFacebookSDK = () => {
  if (typeof window === "undefined") return Promise.resolve(null);
  if (!FB_APP_ID) return Promise.resolve(null);
  if (window.FB) return Promise.resolve(window.FB);
  if (loadingPromise) return loadingPromise;

  loadingPromise = new Promise((resolve) => {
    window.fbAsyncInit = function () {
      window.FB.init({
        appId: FB_APP_ID,
        cookie: true,
        xfbml: true,
        version: "v22.0",
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
 * Returns a promise that resolves with { waba_id, phone_number_id, business_id }
 * captured from the embedded signup `session_info_response` event.
 */
export const launchWhatsAppSignup = async () => {
  const FB = await loadFacebookSDK();
  if (!FB || !WA_CONFIG_ID) {
    throw new Error("FB_NOT_CONFIGURED");
  }

  return new Promise((resolve, reject) => {
    // Capture session_info_response posted by Meta during embedded signup
    const onMessage = (event) => {
      if (event.origin !== "https://www.facebook.com" && event.origin !== "https://web.facebook.com") return;
      try {
        const data = JSON.parse(event.data);
        if (data?.type === "WA_EMBEDDED_SIGNUP" && data?.event === "FINISH") {
          window.removeEventListener("message", onMessage);
          resolve({
            waba_id: data?.data?.waba_id,
            phone_number_id: data?.data?.phone_number_id,
            business_id: data?.data?.business_id,
          });
        }
      } catch (_) {
        // Non-JSON messages are ignored
      }
    };
    window.addEventListener("message", onMessage);

    FB.login(
      (response) => {
        if (!response?.authResponse) {
          window.removeEventListener("message", onMessage);
          reject(new Error("USER_CANCELLED"));
        }
        // session_info_response handled via postMessage above
      },
      {
        config_id: WA_CONFIG_ID,
        response_type: "code",
        override_default_response_type: true,
        extras: { feature: "whatsapp_embedded_signup", version: 2 },
      }
    );
  });
};
