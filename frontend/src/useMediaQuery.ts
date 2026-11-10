// Media query hook (timeline-ui design sections 14 and 15).
import { useEffect, useState } from 'react';

function matches(query: string): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(query).matches;
}

export function useMediaQuery(query: string): boolean {
  const [value, setValue] = useState(() => matches(query));

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return undefined;
    }
    const list = window.matchMedia(query);
    const onChange = (): void => setValue(list.matches);
    onChange();
    list.addEventListener('change', onChange);
    return () => list.removeEventListener('change', onChange);
  }, [query]);

  return value;
}