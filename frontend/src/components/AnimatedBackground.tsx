'use client';

import { useEffect, useRef } from 'react';

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  opacity: number;
}

export default function AnimatedBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let nodes: Node[] = [];
    let lastTime = 0;
    const TARGET_FPS = 30;
    const FRAME_INTERVAL = 1000 / TARGET_FPS;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const createNodes = () => {
      // Reduced node count for better performance
      const count = Math.floor((canvas.width * canvas.height) / 18000);
      nodes = [];
      for (let i = 0; i < count; i++) {
        nodes.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          radius: Math.random() * 1.8 + 0.8,
          opacity: Math.random() * 0.4 + 0.3,
        });
      }
    };

    const drawGradientBackground = (time: number) => {
      const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
      gradient.addColorStop(0, '#0a0f1a');
      gradient.addColorStop(0.3, '#0d1525');
      gradient.addColorStop(0.7, '#0f1a2e');
      gradient.addColorStop(1, '#0a1628');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Ambient glow orbs
      const drawOrb = (x: number, y: number, radius: number, color: string, opacity: number) => {
        const orbGradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
        orbGradient.addColorStop(0, `rgba(${color}, ${opacity})`);
        orbGradient.addColorStop(0.5, `rgba(${color}, ${opacity * 0.3})`);
        orbGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = orbGradient;
        ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
      };

      const t = time * 0.0003;
      drawOrb(
        canvas.width * 0.2 + Math.sin(t) * 100,
        canvas.height * 0.3 + Math.cos(t * 0.7) * 80,
        400,
        '99, 102, 241',
        0.12
      );
      drawOrb(
        canvas.width * 0.8 + Math.cos(t * 0.8) * 120,
        canvas.height * 0.6 + Math.sin(t * 0.6) * 100,
        350,
        '139, 92, 246',
        0.1
      );
      drawOrb(
        canvas.width * 0.5 + Math.sin(t * 0.5) * 80,
        canvas.height * 0.8 + Math.cos(t * 0.4) * 60,
        300,
        '59, 130, 246',
        0.08
      );
      drawOrb(
        canvas.width * 0.7 + Math.cos(t * 0.3) * 60,
        canvas.height * 0.2 + Math.sin(t * 0.9) * 70,
        250,
        '16, 185, 129',
        0.06
      );
    };

    const CONNECTION_DISTANCE = 140;
    const CONNECTION_DISTANCE_SQ = CONNECTION_DISTANCE * CONNECTION_DISTANCE;

    const animate = (currentTime: number) => {
      animationFrameId = requestAnimationFrame(animate);

      // Throttle to target FPS
      const delta = currentTime - lastTime;
      if (delta < FRAME_INTERVAL) return;
      lastTime = currentTime - (delta % FRAME_INTERVAL);

      drawGradientBackground(currentTime);

      // Update nodes
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        node.x += node.vx;
        node.y += node.vy;

        if (node.x < 0 || node.x > canvas.width) node.vx *= -1;
        if (node.y < 0 || node.y > canvas.height) node.vy *= -1;

        node.x = Math.max(0, Math.min(canvas.width, node.x));
        node.y = Math.max(0, Math.min(canvas.height, node.y));
      }

      // Draw connections (optimized with squared distance)
      ctx.lineWidth = 0.7;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const distSq = dx * dx + dy * dy;

          if (distSq < CONNECTION_DISTANCE_SQ) {
            const dist = Math.sqrt(distSq);
            const opacity = (1 - dist / CONNECTION_DISTANCE) * 0.35;

            ctx.beginPath();
            ctx.strokeStyle = `rgba(100, 150, 240, ${opacity})`;
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
          }
        }
      }

      // Draw nodes
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];

        // Simple glow
        const glowGradient = ctx.createRadialGradient(
          node.x, node.y, 0,
          node.x, node.y, node.radius * 5
        );
        glowGradient.addColorStop(0, `rgba(130, 180, 255, ${node.opacity * 0.25})`);
        glowGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = glowGradient;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius * 5, 0, Math.PI * 2);
        ctx.fill();

        // Core dot
        ctx.fillStyle = `rgba(180, 210, 255, ${node.opacity + 0.15})`;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    resize();
    createNodes();
    animationFrameId = requestAnimationFrame(animate);

    const handleResize = () => {
      resize();
      createNodes();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: -1,
      }}
    />
  );
}
