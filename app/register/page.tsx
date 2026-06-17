import { AuthFormCard } from "@/components/auth/AuthFormCard";

export default function RegisterPage() {
  return <AuthFormCard mode="sign-up" devHint={process.env.NODE_ENV === "production" ? null : "本地开发默认管理员：local@slicestudio.dev / slice-studio-local-owner"} />;
}
