import LoginForm from "./LoginForm";

export const metadata = { title: "Sign in — HRCore" };

export default function LoginPage() {
  return (
    <div className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-gray-50 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white">H</div>
          <span className="text-2xl font-bold">HRCore</span>
        </div>
        <div className="card">
          <h1 className="mb-4 text-lg font-semibold">Sign in</h1>
          <LoginForm />
        </div>
        <p className="mt-4 text-center text-xs text-gray-400">
          Demo credentials: any seeded employee email (e.g. lerato@acme.co.za) with password <code className="rounded bg-gray-100 px-1">Acme#2026</code>
        </p>
      </div>
    </div>
  );
}
