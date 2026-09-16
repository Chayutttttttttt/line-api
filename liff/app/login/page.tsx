import LoginCard from "@/components/loginCard";

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[720px] flex-1 items-center justify-center px-4 py-[max(32px,env(safe-area-inset-top),env(safe-area-inset-bottom))] sm:px-6">
      <LoginCard />
    </main>
  );
}
