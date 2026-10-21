/**
 * UI string catalogue. English is complete; other languages fall back to English per key.
 * Hindi strings are a starter set and MUST be reviewed by a native speaker before launch.
 */
export const LANGS = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ", ta: "தமிழ்", te: "తెలుగు", ml: "മലയാളം", mr: "मराठी", bn: "বাংলা" } as const;
export type Lang = keyof typeof LANGS;

const en = {
  emergency: "This is not an emergency service. In a medical emergency call",
  emergencyTail: "or go to the nearest hospital.",
  services: "Services",
  stays: "Stays near hospitals",
  verification: "Nurse verification",
  myCare: "My care",
  book: "Book a nurse",
  nursePortal: "Nurse portal",
  partnerPortal: "Partner portal",
  admin: "Admin",
  account: "Account",
  signIn: "Sign in",
  signOut: "Sign out",
};
type Dict = typeof en;

const hi: Partial<Dict> = {
  emergency: "यह आपातकालीन सेवा नहीं है। चिकित्सा आपात स्थिति में कॉल करें",
  emergencyTail: "या निकटतम अस्पताल जाएँ।",
  services: "सेवाएँ",
  stays: "अस्पताल के पास ठहरने की जगह",
  verification: "नर्स सत्यापन",
  myCare: "मेरी देखभाल",
  book: "नर्स बुक करें",
  account: "खाता",
  signIn: "साइन इन",
  signOut: "साइन आउट",
};

const catalog: Partial<Record<Lang, Partial<Dict>>> = { en, hi };

export function t(lang: string | undefined, key: keyof Dict): string {
  return catalog[(lang as Lang) ?? "en"]?.[key] ?? en[key];
}
