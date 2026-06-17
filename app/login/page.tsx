import { AuthFormCard } from "@/components/auth/AuthFormCard";

export default function LoginPage() {
  return <AuthFormCard mode="sign-in" devHint={process.env.NODE_ENV === "production" ? null : "本地开发默认管理员：local@slicestudio.dev / slice-studio-local-owner"} />;
}
