'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginModal from '@/components/LoginModal';

export default function SignInPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <LoginModal
      isOpen={true}
      onClose={() => router.push('/login')}
      onLoginSuccess={(user) => {
        if (user.role === 'admin') {
          router.push('/admin/dashboard');
        } else {
          router.push('/home');
        }
      }}
      initialMode="register"
      embedded={true}
    />
  );
}
