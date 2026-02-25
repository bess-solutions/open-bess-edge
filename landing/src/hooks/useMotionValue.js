import { useState, useEffect } from 'react'

/**
 * Subscribe to a Framer Motion MotionValue and return its current value as React state.
 */
export default function useMotionValue(motionValue) {
    const [value, setValue] = useState(motionValue.get())
    useEffect(() => motionValue.on('change', v => setValue(Math.min(1, Math.max(0, v))), [motionValue]))
    return [value, setValue]
}
