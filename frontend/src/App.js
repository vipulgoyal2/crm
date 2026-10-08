import { useEffect, useState } from "react";
import axios from "axios";
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LayoutDashboard, ShoppingBag, Users, Package, Factory, CreditCard, Truck, BarChart3, Settings, Search, Plus, Bell, ChevronRight, LogOut, ArrowUpRight, CheckCircle2, Menu, X, Paperclip, CircleDollarSign, Download, Upload, AlertTriangle, Trash2, MessageCircle } from "lucide-react";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const api = axios.create({ baseURL: API, withCredentials: true });
const nav = [{key:"dashboard",label:"Dashboard",icon:LayoutDashboard},{key:"orders",label:"Orders",icon:ShoppingBag},{key:"customers",label:"Customers",icon:Users},{key:"products",label:"Products / SKUs",icon:Package},{key:"production",label:"Production",icon:Factory},{key:"payments",label:"Payments",icon:CreditCard},{key:"shipping",label:"Shipping",icon:Truck},{key:"reports",label:"Reports",icon:BarChart3},{key:"settings",label:"Settings",icon:Settings}];
const money = n => `₹${Number(n || 0).toLocaleString("en-IN", {maximumFractionDigits:0})}`;
const statusClass = s => `status status-${String(s || "").toLowerCase().replaceAll(" ", "-")}`;
const todayLabel = () => new Date().toLocaleDateString("en-IN", {weekday:"long",day:"2-digit",month:"long",year:"numeric"}).toUpperCase();

function waLink(order){
  const phone=String(order.customer_phone||"").replace(/\D/g,"");
  if(!phone) return null;
  const number=phone.length===10?`91${phone}`:phone;
  const items=(order.items&&order.items.length)
    ? order.items.map(i=>`${i.quantity}× ${i.product_name}`).join(", ")
    : (order.product_name||"your order");
  const bits=[`Hi ${order.customer_name}!`,
              `Your Paperbow order ${order.id} (${items}) has shipped${order.courier?` via ${order.courier}`:""}.`];
  if(order.tracking) bits.push(`Track it here: ${order.tracking}`);
  bits.push("Thank you for choosing Paperbow 🎁");
  return `https://wa.me/${number}?text=${encodeURIComponent(bits.join(" "))}`;
}

function Login({onLogin}) {
  const [email,setEmail]=useState("admin@paperbow.in"), [password,setPassword]=useState("Paperbow2026!"), [error,setError]=useState(""), [loading,setLoading]=useState(false);
  const submit=async e=>{e.preventDefault();setLoading(true);setError("");try{const {data}=await api.post("/auth/login",{email,password});onLogin(data)}catch(err){setError(err.response?.data?.detail||"Could not sign in")};setLoading(false)};
  return <main className="login-page"><div className="login-art"><div className="brand-mark large">P<span>·</span></div><div className="art-copy"><p className="eyebrow">PAPERBOW OPERATIONS</p><h1>Make every order<br/><em>feel personal.</em></h1><p>One calm workspace for the orders, people and production behind every gift.</p></div><div className="art-footer">© 2026 Paperbow · Internal workspace</div></div><div className="login-panel"><div className="mobile-brand"><div className="brand-mark">P<span>·</span></div> PAPERBOW</div><div className="login-form-wrap"><p className="eyebrow">WELCOME BACK</p><h2>Sign in to your workspace</h2><p className="muted">Manage today's details with clarity.</p><form onSubmit={submit} data-testid="login-form"><label>Email address<input data-testid="login-email-input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></label><label>Password<input data-testid="login-password-input" type="password" value={password} onChange={e=>setPassword(e.target.value)} required /></label>{error&&<div className="form-error" data-testid="login-error">{error}</div>}<button className="primary-button full" data-testid="login-submit-button" disabled={loading}>{loading?"Signing in…":"Sign in"}<ChevronRight size={17}/></button></form><p className="login-hint">Demo access is ready to explore</p></div></div></main>;
}

function Badge({children,testId}) { return <span className={statusClass(children)} data-testid={testId||`status-${String(children).toLowerCase().replaceAll(" ", "-")}`}>{children}</span> }
function Stat({label,value,delta,icon:Icon,accent}) { return <div className={`stat-card ${accent||""}`} data-testid={`metric-${label.toLowerCase().replaceAll(" ","-")}`}><div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={17}/></span></div><strong>{value}</strong><small><ArrowUpRight size={13}/> {delta}</small></div> }

function Dashboard({data,user,onNavigate}) {
  const chart=data?.revenue_series||[]; const statuses=data?.statuses||{};
  const firstName=(user?.name||"").split(" ")[0]||"there";
  return <div className="page-content"><div className="page-heading"><div><p className="eyebrow" data-testid="dashboard-date">{todayLabel()}</p><h1>Good day, {firstName} <span>✦</span></h1><p className="muted">Here’s the pulse of Paperbow today.</p></div><button className="primary-button" data-testid="new-order-button" onClick={()=>onNavigate("orders") }><Plus size={18}/> New order</button></div><div className="metric-grid"><Stat label="Today's revenue" value={money(data?.today_revenue)} delta="Paid orders today" icon={CircleDollarSign} accent="accent-lilac"/><Stat label="Orders total" value={data?.orders||0} delta={`${money(data?.avg_order_value)} avg`} icon={ShoppingBag} accent="accent-yellow"/><Stat label="Customers" value={data?.customers||0} delta="Confirmed buyers" icon={Users} accent="accent-mint"/><Stat label="Ready to ship" value={statuses["Ready to Ship"]||0} delta="Awaiting courier" icon={Truck} accent="accent-peach"/></div><div className="dashboard-grid"><section className="surface chart-panel"><div className="section-heading"><div><p className="eyebrow">REVENUE OVERVIEW</p><h3>{money(data?.revenue)} <small>total revenue</small></h3></div><select data-testid="dashboard-date-filter"><option>Last 7 days</option><option>This month</option><option>Last month</option></select></div><div className="chart"><ResponsiveContainer width="100%" height={235}><AreaChart data={chart}><defs><linearGradient id="rev" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#456bff" stopOpacity=".22"/><stop offset="100%" stopColor="#456bff" stopOpacity="0"/></linearGradient></defs><XAxis dataKey="label" axisLine={false} tickLine={false} tick={{fill:"#8b93a6",fontSize:12}}/><YAxis hide/><Tooltip formatter={v=>money(v)} contentStyle={{border:"1px solid #e7eaf1",borderRadius:8}}/><Area type="monotone" dataKey="value" stroke="#456bff" strokeWidth={3} fill="url(#rev)"/></AreaChart></ResponsiveContainer></div></section><section className="surface status-panel"><div className="section-heading"><div><p className="eyebrow">ORDER FLOW</p><h3>At a glance</h3></div><button className="text-button" data-testid="view-orders-button" onClick={()=>onNavigate("orders")}>View orders <ChevronRight size={15}/></button></div><div className="flow-list">{[["Confirmed","Orders placed",statuses.Confirmed||0,"#456bff"],["Production","Being crafted",statuses.Production||0,"#e6a53e"],["Quality Check","Almost ready",statuses["Quality Check"]||0,"#7b72df"],["Shipped","On the way",statuses.Shipped||0,"#46a58a"]].map(([a,b,n,c])=><div className="flow-row" key={a}><i style={{background:c}}></i><div><strong>{a}</strong><small>{b}</small></div><b>{n}</b></div>)}</div></section></div><div className="surface recent-panel"><div className="section-heading"><div><p className="eyebrow">RECENT ACTIVITY</p><h3>Latest orders</h3></div><button className="text-button" data-testid="recent-orders-link" onClick={()=>onNavigate("orders")}>See all orders <ChevronRight size={15}/></button></div><OrderTable orders={data?.recent_orders||[]} compact onOpen={()=>onNavigate("orders")}/></div></div>
}

function OrderDetail({order,onClose}) {
  const [detail,setDetail]=useState(order);
  const [note,setNote]=useState("");
  const [file,setFile]=useState(null);
  const [category,setCategory]=useState("Customer Upload");
  const [busy,setBusy]=useState(false);
  const refresh=async()=>{const r=await api.get(`/orders/${order.id}`);setDetail(r.data)};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(()=>{refresh()},[order.id]);
  const update=async(path,body)=>{
    setBusy(true);
    try{
      const url = path==="status" ? `/orders/${order.id}/status?status=${encodeURIComponent(body.status)}` : `/orders/${order.id}/${path}`;
      await api.patch(url, path==="status" ? null : body);
      const r=await api.get(`/orders/${order.id}`);
      setDetail(r.data);
      if(path==="status" && body.status==="Shipped"){
        const link=waLink(r.data);
        if(link) window.open(link,"_blank");
      }
    } finally { setBusy(false); }
  };
  const upload=async()=>{
    if(!file) return;
    setBusy(true);
    try{
      const data=new FormData(); data.append("file",file);
      await api.post(`/orders/${order.id}/files?category=${encodeURIComponent(category)}`,data,{headers:{"Content-Type":"multipart/form-data"}});
      setFile(null);
      await refresh();
    } finally { setBusy(false); }
  };
  const addNote=async()=>{
    if(!note.trim()) return;
    setBusy(true);
    try{
      await api.post(`/orders/${order.id}/notes`,{text:note.trim()});
      setNote("");
      await refresh();
    } finally { setBusy(false); }
  };
  const downloadFile=id=>{ window.open(`${API}/files/${id}`,"_blank"); };
  const notifyWhatsApp=()=>{const link=waLink(detail);if(link) window.open(link,"_blank");};
  const items = detail.items && detail.items.length ? detail.items : (detail.product_name ? [{product_name:detail.product_name, sku:detail.sku, quantity:detail.quantity||1, unit_price:detail.total, customization:detail.customization, line_total:detail.total, tax:0, discount:0}] : []);
  return <div className="modal-backdrop" data-testid="order-detail-modal"><div className="order-detail"><div className="detail-head"><div><p className="eyebrow">ORDER DETAIL / {detail.id}</p><h2>{detail.customer_name}</h2><p className="muted">{detail.customer_phone||"—"} · {new Date(detail.created_at||Date.now()).toLocaleDateString("en-IN")}</p></div><div className="detail-head-actions"><button className="secondary-button wa-button" data-testid="whatsapp-notify-button" disabled={!detail.customer_phone} onClick={notifyWhatsApp}><MessageCircle size={15}/> Notify on WhatsApp</button><button className="icon-button" data-testid="order-detail-close" onClick={onClose}><X size={19}/></button></div></div><div className="detail-badges"><Badge testId="detail-payment-status">{detail.payment_status||"Paid"}</Badge><Badge testId="detail-order-status">{detail.status}</Badge><span className="priority">{detail.priority||"Normal"} priority</span></div><section className="order-items"><p className="eyebrow">ITEMS</p><div className="items-table" data-testid="order-items-list">{items.map((it,i)=><div key={i} className="item-row" data-testid={`order-item-${i}`}><div className="item-main"><strong>{it.quantity}× {it.product_name}</strong><small>{it.sku}{it.customization?` · ${it.customization}`:""}</small></div><div className="item-nums"><small>{money(it.unit_price)} ea{it.discount?` − ${money(it.discount)}`:""}{it.tax_rate?` + ${it.tax_rate}% GST`:""}</small><strong>{money(it.line_total)}</strong></div></div>)}{!items.length&&<small className="muted">No items.</small>}</div><div className="order-totals"><div><small>Subtotal</small><strong>{money(detail.subtotal||detail.total)}</strong></div><div><small>Shipping</small><strong>{money(detail.shipping_cost||0)}</strong></div><div><small>Tax</small><strong>{money(detail.tax||0)}</strong></div><div className="grand"><small>Grand total</small><strong data-testid="order-grand-total">{money(detail.total)}</strong></div></div></section><div className="detail-grid"><section><p className="eyebrow">FILES</p><div className="file-upload"><label data-testid="order-file-input"><Paperclip size={16}/> {file?file.name:"Attach JPG, PNG, WEBP, GIF or PDF"}<input type="file" accept="image/*,.pdf" onChange={e=>setFile(e.target.files[0])}/></label><select data-testid="order-file-category" value={category} onChange={e=>setCategory(e.target.value)}><option>Customer Upload</option><option>Reference</option><option>Design</option><option>Approved Design</option><option>Production File</option></select><button className="secondary-button" disabled={!file||busy} data-testid="order-file-upload-button" onClick={upload}>Upload</button></div><div className="file-list">{(detail.files||[]).map(f=><button key={f.id} className="file-chip" data-testid={`file-chip-${f.id}`} onClick={()=>downloadFile(f.id)}><Paperclip size={13}/>{f.original_filename}<small>{f.category}</small></button>)}{!(detail.files||[]).length&&<small className="muted">No files uploaded yet.</small>}</div></section><section><p className="eyebrow">PAYMENT</p><div className="money-breakdown"><div><small>Order total</small><strong>{money(detail.total)}</strong></div><div><small>Paid</small><strong className="paid-text">{money(detail.amount_paid)}</strong></div><div><small>Pending</small><strong>{money(detail.pending)}</strong></div></div><div className="detail-actions"><button className="secondary-button" disabled={busy} data-testid="payment-mark-paid-button" onClick={()=>update("payment",{amount_paid:detail.total,payment_method:detail.payment_method||"UPI"})}>Mark paid</button></div><p className="eyebrow">OPERATIONS</p><select data-testid="order-status-select" value={detail.status||"Confirmed"} disabled={busy} onChange={e=>update("status",{status:e.target.value})}><option>Confirmed</option><option>Design Required</option><option>Design Approval</option><option>Production</option><option>Quality Check</option><option>Ready to Ship</option><option>Shipped</option><option>Delivered</option><option>Cancelled</option></select><div className="ops-row"><select data-testid="production-status-select" value={detail.production_status||"Waiting"} disabled={busy} onChange={e=>update("operations",{production_status:e.target.value})}><option>Waiting</option><option>Design</option><option>In Production</option><option>Quality Check</option><option>Ready</option></select><select data-testid="shipping-status-select" value={detail.shipping_status||"Not Ready"} disabled={busy} onChange={e=>update("operations",{shipping_status:e.target.value})}><option>Not Ready</option><option>Ready to Ship</option><option>Shipped</option><option>In Transit</option><option>Out for Delivery</option><option>Delivered</option></select></div><input data-testid="order-courier-input" className="ops-input" placeholder="Courier name" defaultValue={detail.courier||""} onBlur={e=>e.target.value!==(detail.courier||"")&&update("operations",{courier:e.target.value})}/><input data-testid="order-tracking-input" className="ops-input" placeholder="Tracking number or URL" defaultValue={detail.tracking||""} onBlur={e=>e.target.value!==(detail.tracking||"")&&update("operations",{tracking:e.target.value})}/></section></div><section className="timeline-section"><p className="eyebrow">TIMELINE</p><div className="timeline">{(detail.timeline||[]).slice().reverse().map((event,i)=><div key={i} data-testid={`timeline-entry-${i}`}><i></i><span><strong>{event.event}</strong>{event.notes&&<em>{event.notes}</em>}<small>{event.user||"Paperbow"} · {new Date(event.date).toLocaleString("en-IN")}</small></span></div>)}{!(detail.timeline||[]).length&&<small className="muted">No events yet.</small>}</div></section><div className="detail-note"><input data-testid="order-note-input" value={note} onChange={e=>setNote(e.target.value)} placeholder="Add an internal note…" onKeyDown={e=>e.key==="Enter"&&addNote()}/><button className="primary-button" data-testid="order-note-button" disabled={!note.trim()||busy} onClick={addNote}>Add note</button></div></div></div>
}

function OrderTable({orders,onOpen}) {
  const [selected,setSelected]=useState(null);
  const safeOrders=orders.filter(o=>String(o.id||"").startsWith("PB-"));
  return <div className="table-wrap"><table><thead><tr><th>Order</th><th>Customer</th><th>Product</th><th>Amount</th><th>Payment</th><th>Status</th><th></th></tr></thead><tbody>{safeOrders.map(o=>{const summary=o.items&&o.items.length>1?`${o.items.length} items · ${o.items[0].product_name}…`:(o.items&&o.items[0]?.product_name)||o.product_name||o.sku;const avatar=(summary||"P")[0];return <tr key={o.id} data-testid={`order-row-${o.id}`}><td><strong className="order-id">{o.id}</strong><small>{new Date(o.created_at||Date.now()).toLocaleDateString("en-IN")}</small></td><td>{o.customer_name}</td><td><span className="product-cell"><span className="product-dot">{avatar}</span>{summary}</span></td><td><strong>{money(o.total)}</strong></td><td><Badge testId={`payment-status-${o.id}`}>{o.payment_status||"Paid"}</Badge></td><td><Badge testId={`order-status-${o.id}`}>{o.status}</Badge></td><td><button className="icon-button" aria-label="Open order" data-testid={`open-order-${o.id}`} onClick={()=>{setSelected(o);onOpen&&onOpen(o)}}><ChevronRight size={16}/></button></td></tr>})}</tbody></table>{!safeOrders.length&&<div className="empty">No orders found.</div>}{selected&&<OrderDetail order={selected} onClose={()=>setSelected(null)}/>}</div>
}

function AddRecordForm({type,onClose}) {
  const customer=type==="customers";
  const [form,setForm]=useState(customer?{name:"",phone:"",email:"",city:"",state:""}:{sku:"",name:"",category:"Frames",selling_price:"",cost_price:"",stock:"",production_method:"Laser"});
  const [error,setError]=useState("");
  const submit=async e=>{e.preventDefault();try{await api.post(`/${type}`,customer?form:{...form,selling_price:Number(form.selling_price),cost_price:Number(form.cost_price||0),stock:Number(form.stock||0)});window.location.reload()}catch(err){setError(err.response?.data?.detail||"Please check the details")}};
  return <div className="modal-backdrop" data-testid={`${type}-form-modal`}><form className="modal" onSubmit={submit}><div className="modal-head"><div><p className="eyebrow">PAPERBOW / NEW {customer?"CUSTOMER":"SKU"}</p><h2>{customer?"Add customer":"Add product SKU"}</h2></div><button type="button" className="icon-button" data-testid={`${type}-form-close`} onClick={onClose}><X size={18}/></button></div>{error&&<div className="form-error">{error}</div>}<div className="form-grid">{(customer?[["name","Full name"],["phone","Phone number"],["email","Email"],["city","City"],["state","State"]]:[["sku","SKU code"],["name","Product name"],["category","Category"],["selling_price","Selling price"],["cost_price","Cost price"],["stock","Stock quantity"],["production_method","Production method"]]).map(([key,label])=><label key={key}>{label}<input data-testid={`${type}-${key}-input`} required={customer?["name","phone"].includes(key):["sku","name","category","selling_price"].includes(key)} value={form[key]} onChange={e=>setForm({...form,[key]:e.target.value})}/></label>)}</div><div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} data-testid={`${type}-form-cancel`}>Cancel</button><button className="primary-button" data-testid={`${type}-form-submit`}>Save {customer?"customer":"SKU"}</button></div></form></div>
}

function NewOrderForm({onClose,onCreated}){
  const [customers,setCustomers]=useState([]);
  const [products,setProducts]=useState([]);
  const [customerId,setCustomerId]=useState("");
  const [customerFilter,setCustomerFilter]=useState("");
  const [channel,setChannel]=useState("Instagram");
  const [priority,setPriority]=useState("Normal");
  const [shippingCost,setShippingCost]=useState(0);
  const [paymentMethod,setPaymentMethod]=useState("UPI");
  const [amountPaid,setAmountPaid]=useState(0);
  const [items,setItems]=useState([{product_id:"",quantity:1,customization:"",discount:0,tax_rate:18}]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{
    Promise.all([api.get("/customers"),api.get("/products")]).then(([c,p])=>{setCustomers(c.data);setProducts(p.data)});
  },[]);
  const setItem=(i,patch)=>setItems(x=>x.map((it,j)=>j===i?{...it,...patch}:it));
  const addItem=()=>setItems(x=>[...x,{product_id:"",quantity:1,customization:"",discount:0,tax_rate:18}]);
  const removeItem=i=>setItems(x=>x.filter((_,j)=>j!==i));
  const subtotal=items.reduce((s,it)=>{const p=products.find(x=>x.id===it.product_id);if(!p)return s;return s+Math.max(p.selling_price*Number(it.quantity||0)-Number(it.discount||0),0)},0);
  const tax=items.reduce((s,it)=>{const p=products.find(x=>x.id===it.product_id);if(!p)return s;const g=Math.max(p.selling_price*Number(it.quantity||0)-Number(it.discount||0),0);return s+g*Number(it.tax_rate||0)/100},0);
  const grand=subtotal+tax+Number(shippingCost||0);
  const filteredCustomers=customerFilter?customers.filter(c=>(c.name+c.phone).toLowerCase().includes(customerFilter.toLowerCase())):customers;
  const submit=async e=>{
    e.preventDefault();setError("");
    if(!customerId){setError("Pick a customer");return}
    const valid=items.filter(i=>i.product_id);
    if(!valid.length){setError("Add at least one product");return}
    setBusy(true);
    try{
      const payload={customer_id:customerId,items:valid.map(i=>({product_id:i.product_id,quantity:Number(i.quantity||1),customization:i.customization||"",discount:Number(i.discount||0),tax_rate:Number(i.tax_rate||0)})),channel,priority,shipping_cost:Number(shippingCost||0),payment_method:paymentMethod,amount_paid:Number(amountPaid||0)};
      const {data}=await api.post("/orders",payload);
      onCreated&&onCreated(data);
      onClose();
    }catch(err){setError(err.response?.data?.detail||"Could not create order")}
    setBusy(false);
  };
  return <div className="modal-backdrop" data-testid="orders-form-modal"><form className="modal order-modal" onSubmit={submit}>
    <div className="modal-head"><div><p className="eyebrow">PAPERBOW / NEW ORDER</p><h2>Create a confirmed order</h2></div><button type="button" className="icon-button" data-testid="orders-form-close" onClick={onClose}><X size={18}/></button></div>
    {error&&<div className="form-error" data-testid="orders-form-error">{error}</div>}
    <div className="order-form-section"><p className="eyebrow">CUSTOMER</p><input placeholder="Search customers by name or phone" data-testid="order-customer-search" value={customerFilter} onChange={e=>setCustomerFilter(e.target.value)}/><div className="customer-picker" data-testid="order-customer-picker">{filteredCustomers.slice(0,6).map(c=><button type="button" key={c.id} className={customerId===c.id?"picked":""} data-testid={`order-customer-${c.id}`} onClick={()=>setCustomerId(c.id)}><strong>{c.name}</strong><small>{c.phone}</small></button>)}{!filteredCustomers.length&&<small className="muted">No match.</small>}</div></div>
    <div className="order-form-section"><div className="section-heading"><p className="eyebrow">ITEMS</p><button type="button" className="text-button" data-testid="order-add-item" onClick={addItem}><Plus size={13}/> Add item</button></div>{items.map((it,i)=>{const p=products.find(x=>x.id===it.product_id);const g=p?Math.max(p.selling_price*Number(it.quantity||0)-Number(it.discount||0),0):0;const tx=p?g*Number(it.tax_rate||0)/100:0;return <div key={i} className="order-item-row" data-testid={`order-form-item-${i}`}><select data-testid={`order-item-product-${i}`} value={it.product_id} onChange={e=>setItem(i,{product_id:e.target.value})}><option value="">Pick product</option>{products.map(p=><option key={p.id} value={p.id}>{p.sku} · {p.name} · {money(p.selling_price)}</option>)}</select><input type="number" min="1" data-testid={`order-item-qty-${i}`} value={it.quantity} onChange={e=>setItem(i,{quantity:e.target.value})} placeholder="Qty"/><input data-testid={`order-item-custom-${i}`} value={it.customization} onChange={e=>setItem(i,{customization:e.target.value})} placeholder="Customization"/><input type="number" min="0" data-testid={`order-item-discount-${i}`} value={it.discount} onChange={e=>setItem(i,{discount:e.target.value})} placeholder="Disc"/><input type="number" min="0" step="0.1" data-testid={`order-item-tax-${i}`} value={it.tax_rate} onChange={e=>setItem(i,{tax_rate:e.target.value})} placeholder="GST %"/><div className="line-total">{money(g+tx)}</div><button type="button" className="icon-button" data-testid={`order-item-remove-${i}`} onClick={()=>removeItem(i)} disabled={items.length===1}><Trash2 size={14}/></button></div>})}</div>
    <div className="order-form-section"><div className="order-form-grid"><label>Sales channel<select data-testid="order-channel-select" value={channel} onChange={e=>setChannel(e.target.value)}><option>Instagram</option><option>WhatsApp</option><option>Website</option><option>Referral</option><option>Offline</option><option>Other</option></select></label><label>Priority<select data-testid="order-priority-select" value={priority} onChange={e=>setPriority(e.target.value)}><option>Normal</option><option>High</option><option>Urgent</option></select></label><label>Shipping cost<input type="number" min="0" data-testid="order-shipping-input" value={shippingCost} onChange={e=>setShippingCost(e.target.value)}/></label><label>Payment method<select data-testid="order-payment-method-select" value={paymentMethod} onChange={e=>setPaymentMethod(e.target.value)}><option>UPI</option><option>Bank Transfer</option><option>Card</option><option>Cash</option><option>Other</option></select></label><label>Amount paid<input type="number" min="0" data-testid="order-amount-paid-input" value={amountPaid} onChange={e=>setAmountPaid(e.target.value)}/></label></div></div>
    <div className="order-form-totals" data-testid="order-form-totals"><div><small>Subtotal</small><strong>{money(subtotal)}</strong></div><div><small>Shipping</small><strong>{money(Number(shippingCost||0))}</strong></div><div><small>Tax</small><strong>{money(tax)}</strong></div><div className="grand"><small>Grand total</small><strong>{money(grand)}</strong></div></div>
    <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} data-testid="orders-form-cancel">Cancel</button><button className="primary-button" data-testid="orders-form-submit" disabled={busy}>{busy?"Creating…":"Create order"}</button></div>
  </form></div>
}

function ImportWizard({kind,onClose,onDone}) {
  const [step,setStep]=useState("pick"); // pick | review | done
  const [file,setFile]=useState(null);
  const [preview,setPreview]=useState(null);
  const [result,setResult]=useState(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const runPreview=async()=>{
    if(!file){setError("Choose a CSV file first");return}
    setBusy(true);setError("");
    try{
      const body=new FormData(); body.append("file",file);
      const {data}=await api.post(`/import/${kind}/preview`,body,{headers:{"Content-Type":"multipart/form-data"}});
      setPreview(data); setStep("review");
    }catch(err){setError(err.response?.data?.detail||"Could not read CSV")}
    setBusy(false);
  };
  const commit=async()=>{
    setBusy(true);setError("");
    try{
      const {data}=await api.post(`/import/${kind}`,{rows:preview.rows,skip_duplicates:true});
      setResult(data); setStep("done"); onDone&&onDone();
    }catch(err){setError(err.response?.data?.detail||"Import failed")}
    setBusy(false);
  };
  return <div className="modal-backdrop" data-testid="import-wizard-modal"><div className="modal import-modal">
    <div className="modal-head"><div><p className="eyebrow">PAPERBOW / IMPORT {kind.toUpperCase()}</p><h2>CSV import wizard</h2></div><button type="button" className="icon-button" data-testid="import-wizard-close" onClick={onClose}><X size={18}/></button></div>
    <ol className="wizard-steps"><li className={step==="pick"?"active":step==="review"||step==="done"?"done":""}>1 · Upload</li><li className={step==="review"?"active":step==="done"?"done":""}>2 · Review</li><li className={step==="done"?"active":""}>3 · Confirm</li></ol>
    {error&&<div className="form-error" data-testid="import-wizard-error">{error}</div>}
    {step==="pick"&&<div className="wizard-body"><p className="muted">Upload a UTF-8 CSV. Required columns: <strong>{kind==="customers"?"name, phone":kind==="products"?"sku, name, category, selling_price":"id, customer_name, total"}</strong>. Duplicate {kind==="customers"?"phones":kind==="products"?"SKUs":"order IDs"} are skipped.</p><label className="wizard-dropzone" data-testid="import-wizard-file"><Upload size={20}/><span>{file?file.name:"Choose a CSV file"}</span><input type="file" accept=".csv" onChange={e=>setFile(e.target.files[0])}/></label><div className="modal-actions"><button className="secondary-button" onClick={onClose} data-testid="import-wizard-cancel">Cancel</button><button className="primary-button" disabled={!file||busy} data-testid="import-wizard-next" onClick={runPreview}>{busy?"Reading…":"Review file"}</button></div></div>}
    {step==="review"&&preview&&<div className="wizard-body"><div className="wizard-stats"><div><strong>{preview.total}</strong><small>rows</small></div><div><strong className="paid-text">{preview.valid}</strong><small>ready to import</small></div><div><strong>{preview.errors.length}</strong><small>validation errors</small></div><div><strong>{preview.duplicates.length}</strong><small>duplicate {preview.unique_field}</small></div></div>{preview.errors.length>0&&<div className="wizard-errors" data-testid="import-wizard-errors"><p className="eyebrow"><AlertTriangle size={12}/> ROWS WITH ERRORS</p><ul>{preview.errors.map(e=><li key={e.row}>Row {e.row} · missing {e.missing.join(", ")}</li>)}</ul></div>}{preview.duplicates.length>0&&<div className="wizard-dupes" data-testid="import-wizard-dupes"><p className="eyebrow">DUPLICATES (will be skipped)</p><ul>{preview.duplicates.map(d=><li key={d.row}>Row {d.row} · {preview.unique_field}: {d[preview.unique_field]}</li>)}</ul></div>}{preview.sample_rows.length>0&&<div className="wizard-table" data-testid="import-wizard-preview"><p className="eyebrow">PREVIEW ({preview.valid} rows)</p><table><thead><tr>{preview.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{preview.sample_rows.map((r,i)=><tr key={i}>{preview.columns.map(c=><td key={c}>{String(r[c]||"—")}</td>)}</tr>)}</tbody></table></div>}<div className="modal-actions"><button className="secondary-button" onClick={()=>setStep("pick")} data-testid="import-wizard-back">Back</button><button className="primary-button" disabled={!preview.valid||busy} data-testid="import-wizard-confirm" onClick={commit}>{busy?"Importing…":`Import ${preview.valid} rows`}</button></div></div>}
    {step==="done"&&result&&<div className="wizard-body wizard-done" data-testid="import-wizard-done"><CheckCircle2 size={38}/><h3>Import complete</h3><p className="muted">Added {result.inserted} rows. Skipped {result.skipped_duplicates} duplicates.</p><div className="modal-actions"><button className="primary-button" onClick={onClose} data-testid="import-wizard-finish">Done</button></div></div>}
  </div></div>
}

function Records({type,items,onSearch,onFilter,onAdd,onNavigate,status,setStatus}) {
  const isOrders=type==="orders";
  const [showForm,setShowForm]=useState(false);
  const [showNewOrder,setShowNewOrder]=useState(false);
  const [showImport,setShowImport]=useState(false);
  const title=isOrders?"Orders":type==="customers"?"Customers":"Products & SKUs";
  const subtitle=isOrders?"Every confirmed order, from paid to delivered.":type==="customers"?"Your customer relationships, in one place.":"The products that make Paperbow memorable.";
  const exportCsv=()=>window.open(`${API}/export/${type}`,"_blank");
  return <div className="page-content"><div className="page-heading"><div><p className="eyebrow">PAPERBOW / {type.toUpperCase()}</p><h1>{title}</h1><p className="muted">{subtitle}</p></div><div className="header-actions"><button className="secondary-button" data-testid={`import-${type}-button`} onClick={()=>setShowImport(true)}><Upload size={15}/> Import</button><button className="secondary-button" data-testid={`export-${type}-button`} onClick={exportCsv}><Download size={15}/> Export</button><button className="primary-button" data-testid={`add-${type}-button`} onClick={()=>isOrders?setShowNewOrder(true):setShowForm(true)}><Plus size={18}/> Add {isOrders?"order":type==="products"?"SKU":"customer"}</button></div></div><div className="toolbar"><div className="search-box"><Search size={17}/><input data-testid={`${type}-search-input`} placeholder={`Search ${type}…`} onChange={e=>onSearch(e.target.value)}/></div>{isOrders&&<select data-testid="order-status-filter" value={status} onChange={e=>setStatus(e.target.value)}><option>All</option><option>Confirmed</option><option>Design Required</option><option>Production</option><option>Quality Check</option><option>Ready to Ship</option><option>Shipped</option><option>Delivered</option><option>Cancelled</option></select>}</div>{isOrders?<div className="surface table-surface"><OrderTable orders={items} onOpen={()=>onNavigate("orders")}/></div>:<div className="surface table-surface"><table><thead><tr>{type==="customers"?<><th>Customer</th><th>Contact</th><th>Location</th><th>Orders</th><th>Total spent</th><th>Type</th><th></th></>:<><th>SKU</th><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Method</th><th></th></>}</tr></thead><tbody>{items.map(x=><tr key={x.id}>{type==="customers"?<><td><div className="person"><span className="avatar">{x.name?.split(" ").map(y=>y[0]).join("")}</span><strong>{x.name}</strong></div></td><td>{x.phone}<small>{x.email}</small></td><td>{x.city}{x.state?`, ${x.state}`:""}</td><td>{x.orders||0}</td><td><strong>{money(x.spent)}</strong></td><td><Badge testId={`customer-type-${x.id}`}>{x.type||"New"}</Badge></td><td><button className="icon-button" data-testid={`customer-${x.id}-open`}><ChevronRight size={16}/></button></td></>:<><td><strong className="sku">{x.sku}</strong></td><td><strong>{x.name}</strong><small>{x.description||"Personalized Paperbow product"}</small></td><td>{x.category}</td><td><strong>{money(x.selling_price)}</strong><small>Cost {money(x.cost_price)}</small></td><td><span className={x.stock<10?"stock low":"stock"}>{x.stock||0} units</span></td><td>{x.production_method}</td><td><button className="icon-button" data-testid={`product-${x.id}-open`}><ChevronRight size={16}/></button></td></>}</tr>)}</tbody></table>{!items.length&&<div className="empty">Nothing here yet.</div>}</div>}{showForm&&<AddRecordForm type={type} onClose={()=>setShowForm(false)}/>}{showNewOrder&&<NewOrderForm onClose={()=>setShowNewOrder(false)} onCreated={()=>{setShowNewOrder(false);onFilter&&onFilter()}}/>}{showImport&&<ImportWizard kind={type} onClose={()=>setShowImport(false)} onDone={onFilter}/>}</div>
}

function RetentionInsights({onNavigate}) {
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{api.get("/retention").then(r=>setData(r.data)).catch(err=>setError(err.response?.data?.detail||"Could not load retention insights"))},[]);
  return <div className="page-content"><div className="page-heading"><div><p className="eyebrow">PAPERBOW / REPORTS</p><h1>Customer retention</h1><p className="muted">Know who comes back, what they love, and where service can feel more personal.</p></div><button className="primary-button" data-testid="reports-orders-button" onClick={()=>onNavigate("orders")}><ShoppingBag size={17}/> Open orders</button></div>{error&&<div className="form-error" data-testid="retention-error">{error}</div>}<div className="metric-grid"><Stat label="Repeat purchase rate" value={`${data?.repeat_rate||0}%`} delta="Customers with 2+ orders" icon={Users} accent="accent-mint"/><Stat label="Returning customers" value={data?.returning_customers||0} delta="Relationships growing" icon={ArrowUpRight} accent="accent-lilac"/><Stat label="VIP customers" value={data?.vip_customers||0} delta="₹5,000+ lifetime spend" icon={CircleDollarSign} accent="accent-yellow"/><Stat label="Total customers" value={data?.total_customers||0} delta="Confirmed buyers only" icon={CheckCircle2} accent="accent-peach"/></div><div className="reports-grid"><section className="surface report-panel"><div className="section-heading"><div><p className="eyebrow">TOP CUSTOMERS</p><h3>Relationships worth remembering</h3></div></div><div className="retention-list">{(data?.top_customers||[]).map((c,i)=><div key={c.name} data-testid={`retention-customer-${i}`}><span className="avatar">{c.name?.split(" ").map(x=>x[0]).join("")}</span><div><strong>{c.name}</strong><small>{c.orders||0} orders · {c.type||"New"}</small></div><b>{money(c.spent)}</b></div>)}{!(data?.top_customers||[]).length&&<small className="muted">Nothing to show yet.</small>}</div></section><section className="surface report-panel"><div className="section-heading"><div><p className="eyebrow">DATA WORKSPACE</p><h3>CSV workflows</h3></div></div><p className="muted report-copy">Export a clean snapshot or run the import wizard with validation and duplicate protection.</p><div className="csv-grid">{["customers","products","orders"].map(kind=><div key={kind} className="csv-row"><strong>{kind}</strong><button className="text-button" data-testid={`export-${kind}-csv`} onClick={()=>window.open(`${API}/export/${kind}`,"_blank")}><Download size={13}/> Export</button><button className="text-button" data-testid={`import-${kind}-csv`} onClick={()=>onNavigate(kind)}><Upload size={13}/> Open wizard</button></div>)}</div></section></div></div>
}

function Placeholder({type,onNavigate}) {
  if(type==="reports") return <RetentionInsights onNavigate={onNavigate}/>;
  const cards={production:[Factory,"Production board","Keep every personalized order moving from design to dispatch.","Open orders to update production"],payments:[CreditCard,"Payments","A clear view of paid, pending and reconciled orders.","Open an order to record payment"],shipping:[Truck,"Shipping","Track every parcel from ready-to-ship to delivered.","Open an order to add tracking"],settings:[Settings,"Settings","Workspace preferences and team access.","Admin access"]};
  const [Icon,title,copy,stat]=cards[type]||cards.production;
  return <div className="page-content"><div className="page-heading"><div><p className="eyebrow">PAPERBOW / {type.toUpperCase()}</p><h1>{title}</h1><p className="muted">{copy}</p></div><button className="primary-button" data-testid={`${type}-quick-action`} onClick={()=>onNavigate("orders")}><Plus size={18}/> Quick action</button></div><div className="feature-empty surface"><div className="feature-icon"><Icon size={28}/></div><p className="eyebrow">INTERNAL WORKSPACE</p><h2>{stat}</h2><p>This view is connected to the same order relationships as your dashboard. Start with an order and the operational trail stays together.</p><button className="secondary-button" data-testid={`${type}-orders-link`} onClick={()=>onNavigate("orders")}>Open orders <ChevronRight size={16}/></button></div></div>
}

function App(){
  const [user,setUser]=useState(null);
  const [checking,setChecking]=useState(true);
  const [page,setPage]=useState("dashboard");
  const [data,setData]=useState(null);
  const [items,setItems]=useState([]);
  const [search,setSearch]=useState("");
  const [status,setStatus]=useState("All");
  const [mobile,setMobile]=useState(false);
  useEffect(()=>{api.get("/auth/me").then(r=>setUser(r.data)).catch(()=>{}).finally(()=>setChecking(false))},[]);
  useEffect(()=>{
    if(!user) return;
    let cancelled=false;
    const load=async()=>{
      if(page==="dashboard"){const r=await api.get("/dashboard"); if(!cancelled) setData(r.data)}
      else if(["orders","customers","products"].includes(page)){
        const params=new URLSearchParams();
        if(search) params.set("search",search);
        if(page==="orders"&&status) params.set("status",status);
        const r=await api.get(`/${page}?${params}`);
        if(!cancelled) setItems(r.data);
      }
    };
    load();
    return ()=>{cancelled=true}
  },[user,page,search,status]);
  if(checking) return <div className="loading-screen">Loading Paperbow<span>·</span></div>;
  if(!user) return <Login onLogin={setUser}/>;
  const navTo=k=>{setPage(k);setSearch("");setStatus("All");setMobile(false)};
  const content = page==="dashboard"
    ? <Dashboard data={data} user={user} onNavigate={navTo}/>
    : ["orders","customers","products"].includes(page)
      ? <Records type={page} items={items} status={status} setStatus={setStatus} onSearch={setSearch} onFilter={()=>setSearch(s=>s+"")} onAdd={()=>navTo("orders")} onNavigate={navTo}/>
      : <Placeholder type={page} onNavigate={navTo}/>;
  const initials=(user.name||"A").split(" ").map(x=>x[0]).join("").slice(0,2).toUpperCase();
  return <div className="app-shell"><aside className={mobile?"sidebar open":"sidebar"}><div className="sidebar-head"><div className="brand-mark">P<span>·</span></div><strong>PAPERBOW</strong><button className="close-mobile" onClick={()=>setMobile(false)} data-testid="close-sidebar-button"><X size={18}/></button></div><div className="workspace-switcher"><span className="workspace-avatar">P</span><div><strong>Paperbow HQ</strong><small>Operations workspace</small></div><ChevronRight size={15}/></div><nav>{nav.map(({key,label,icon:Icon})=><button key={key} className={page===key?"active":""} data-testid={`nav-${key}`} onClick={()=>navTo(key)}><Icon size={17}/><span>{label}</span>{key==="orders"&&data?.orders?<i>{data.orders}</i>:null}</button>)}</nav><div className="sidebar-bottom"><div className="mini-profile"><span className="avatar">{initials}</span><div><strong>{user.name}</strong><small>{user.role?.charAt(0).toUpperCase()+user.role?.slice(1)}</small></div><button data-testid="logout-button" onClick={async()=>{await api.post("/auth/logout");setUser(null)}}><LogOut size={15}/></button></div></div></aside><main className="main"><header className="topbar"><button className="mobile-menu" data-testid="open-sidebar-button" onClick={()=>setMobile(true)}><Menu size={20}/></button><div className="global-search"><Search size={17}/><input data-testid="global-search-input" placeholder="Search anything…"/><kbd>⌘ K</kbd></div><div className="top-actions"><button className="round-button" data-testid="notifications-button"><Bell size={18}/><i></i></button><div className="top-divider"></div><span className="top-avatar">{initials}</span><strong>{user.name?.split(" ")[0]}</strong></div></header>{content}</main></div>
}

export default App;
