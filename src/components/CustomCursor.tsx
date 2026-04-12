import { useEffect, useState } from "react"
import { motion, useSpring } from "framer-motion"

export default function CustomCursor() {
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [clicked, setClicked] = useState(false)
  const [hovered, setHovered] = useState(false)

  // Use framer-motion springs for that physics-based snappy delay
  const springConfig = { damping: 25, stiffness: 300, mass: 0.5 }
  const cursorX = useSpring(0, springConfig)
  const cursorY = useSpring(0, springConfig)

  useEffect(() => {
    const moveCursor = (e: MouseEvent) => {
      setPosition({ x: e.clientX, y: e.clientY })
      cursorX.set(e.clientX - 16) // center offset (32/2)
      cursorY.set(e.clientY - 16)
    }
    
    const handleTagHover = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (
        target.tagName.toLowerCase() === "a" || 
        target.tagName.toLowerCase() === "button" ||
        target.closest("a") || 
        target.closest("button")
      ) {
        setHovered(true)
      } else {
        setHovered(false)
      }
    }

    const mouseDown = () => setClicked(true)
    const mouseUp = () => setClicked(false)

    window.addEventListener("mousemove", moveCursor)
    window.addEventListener("mousemove", handleTagHover)
    window.addEventListener("mousedown", mouseDown)
    window.addEventListener("mouseup", mouseUp)

    return () => {
      window.removeEventListener("mousemove", moveCursor)
      window.removeEventListener("mousemove", handleTagHover)
      window.removeEventListener("mousedown", mouseDown)
      window.removeEventListener("mouseup", mouseUp)
    }
  }, [cursorX, cursorY])

  return (
    <>
      <motion.div
        className="fixed top-0 left-0 w-8 h-8 rounded-full border border-primary pointer-events-none z-[9999] mix-blend-difference"
        style={{
          x: cursorX,
          y: cursorY,
          scale: clicked ? 0.8 : hovered ? 1.5 : 1,
          backgroundColor: hovered ? "rgba(18, 184, 134, 0.2)" : "transparent",
        }}
        transition={{ scale: { type: "spring", stiffness: 300, damping: 20 } }}
      />
      {/* Tiny center dot */}
      <motion.div
        className="fixed top-0 left-0 w-1.5 h-1.5 bg-primary rounded-full pointer-events-none z-[9999]"
        style={{
          x: position.x - 3,
          y: position.y - 3,
        }}
        transition={{ type: "tween", ease: "linear", duration: 0 }}
      />
    </>
  )
}
