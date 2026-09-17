import liff from "@line/liff";

let initialization: Promise<void> | undefined;

export async function initliff() {
    const liffId = process.env.NEXT_PUBLIC_LIFF_ID;

    if (!liffId) {
        throw new Error("NEXT_PUBLIC_LIFF_ID not defined");
    }

    if (!initialization) {
        initialization = liff.init({ liffId }).catch((error: unknown) => {
            initialization = undefined;
            throw error;
        });
    }

    await initialization;
}

export function loginWithLine() {
    if (!liff.isLoggedIn()) {
        liff.login();
    }
}

export function logoutLine() {
    if (liff.isLoggedIn()) {
        liff.logout();
    }
}

export function getLineIdToken() {
    return liff.getIDToken();
}

export function isLineLoggedIn() {
    return liff.isLoggedIn()
}
