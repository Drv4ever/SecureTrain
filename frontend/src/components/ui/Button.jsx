import React from 'react'

export function Button({ variant = 'default', size = 'default', className = '', ...props }) {
  return <button className={`ui-button ui-button-${variant} ui-button-${size} ${className}`} {...props} />
}

export function Badge({ children, variant = 'default', className = '' }) {
  return <span className={`ui-badge ui-badge-${variant} ${className}`}>{children}</span>
}
