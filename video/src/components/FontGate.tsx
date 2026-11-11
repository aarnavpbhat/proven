import { useEffect, useState } from 'react';
import { continueRender, delayRender } from 'remotion';
import { fontsReady } from '../brand/fonts';

// Renders children only after all fonts load, so text measurement is exact on every frame.
export const FontGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [handle] = useState(() => delayRender('Loading fonts'));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    fontsReady.then(() => {
      setReady(true);
      continueRender(handle);
    });
  }, [handle]);
  return ready ? <>{children}</> : null;
};
