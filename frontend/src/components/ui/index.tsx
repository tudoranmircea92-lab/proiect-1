import React from 'react'

export const Card = ({ children, className='' }: any) => <section className={`bg-white border border-slate-200 rounded-xl shadow-sm p-4 ${className}`}>{children}</section>
export const Button = ({ children, variant='default', className='', ...props }: any) => <button className={`${variant==='default'?'bg-blue-600 text-white hover:bg-blue-700':'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'} px-3 py-2 rounded-md text-sm disabled:opacity-50 ${className}`} {...props}>{children}</button>
export const Badge = ({ children, className='' }: any) => <span className={`inline-flex px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-700 ${className}`}>{children}</span>
export const Input = (props: any) => <input className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" {...props} />
export const Select = ({ children, ...props }: any) => <select className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm" {...props}>{children}</select>
export const Switch = ({ checked, onCheckedChange }: any) => <button onClick={()=>onCheckedChange(!checked)} className={`w-10 h-6 rounded-full ${checked?'bg-blue-600':'bg-slate-300'} relative`}><span className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-all ${checked?'left-5':'left-1'}`}></span></button>
export const Accordion = ({ title, children }: any) => <details className="border border-slate-200 rounded-md p-3"><summary className="cursor-pointer text-sm font-medium">{title}</summary><div className="mt-3">{children}</div></details>
export const Progress = ({ value }: { value: number }) => <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden"><div className="h-full bg-blue-600" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
export const Skeleton = ({ className='' }: any) => <div className={`animate-pulse bg-slate-200 rounded ${className}`} />
export const Alert = ({ children, variant='default' }: any) => <div className={`${variant==='destructive'?'bg-red-50 border-red-200 text-red-700':'bg-slate-50 border-slate-200 text-slate-700'} border rounded-md p-3 text-sm`}>{children}</div>

export function Tabs({ tabs, active, setActive }: { tabs: string[]; active: string; setActive: (x: string)=>void }) {
  return <div className='flex gap-1 border-b border-slate-200'>{tabs.map(t=><button key={t} onClick={()=>setActive(t)} className={`px-3 py-2 text-sm ${active===t?'border-b-2 border-blue-600 text-blue-700 font-medium':'text-slate-600'}`}>{t}</button>)}</div>
}
