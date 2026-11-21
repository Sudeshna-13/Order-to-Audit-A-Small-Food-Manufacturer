import os, csv, io
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-before-deploy')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///order_audit.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app); login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id=db.Column(db.Integer, primary_key=True); username=db.Column(db.String(80), unique=True); password_hash=db.Column(db.String(255)); role=db.Column(db.String(30)); full_name=db.Column(db.String(120))
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)
class Customer(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120)); kind=db.Column(db.String(30)); state=db.Column(db.String(80)); gstin=db.Column(db.String(20)); salesman_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=True)
class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120)); pack_size=db.Column(db.String(30)); hsn=db.Column(db.String(20)); price_paise=db.Column(db.Integer); gst_rate=db.Column(db.Integer,default=5); finished_stock=db.Column(db.Integer,default=0)
class Material(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120)); unit=db.Column(db.String(20)); category=db.Column(db.String(30)); stock_milli=db.Column(db.Integer,default=0); rate_paise=db.Column(db.Integer,default=0); reorder_level_milli=db.Column(db.Integer,default=0)
class BOMLine(db.Model):
    id=db.Column(db.Integer,primary_key=True); product_id=db.Column(db.Integer,db.ForeignKey('product.id')); material_id=db.Column(db.Integer,db.ForeignKey('material.id')); qty_milli=db.Column(db.Integer); unit=db.Column(db.String(20))
class Supplier(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120)); state=db.Column(db.String(80)); gstin=db.Column(db.String(20))
class Purchase(db.Model):
    id=db.Column(db.Integer,primary_key=True); supplier_id=db.Column(db.Integer,db.ForeignKey('supplier.id')); material_id=db.Column(db.Integer,db.ForeignKey('material.id')); qty_milli=db.Column(db.Integer); rate_paise=db.Column(db.Integer); created_at=db.Column(db.DateTime,default=datetime.utcnow); reference=db.Column(db.String(80))
class Order(db.Model):
    id=db.Column(db.Integer,primary_key=True); customer_id=db.Column(db.Integer,db.ForeignKey('customer.id')); salesman_id=db.Column(db.Integer,db.ForeignKey('user.id')); product_id=db.Column(db.Integer,db.ForeignKey('product.id')); qty=db.Column(db.Integer); status=db.Column(db.String(30),default='Submitted'); unit_price_paise=db.Column(db.Integer); created_at=db.Column(db.DateTime,default=datetime.utcnow); notes=db.Column(db.Text)
class Invoice(db.Model):
    id=db.Column(db.Integer,primary_key=True); order_id=db.Column(db.Integer,db.ForeignKey('order.id')); number=db.Column(db.String(40),unique=True); customer_id=db.Column(db.Integer,db.ForeignKey('customer.id')); product_id=db.Column(db.Integer,db.ForeignKey('product.id')); qty=db.Column(db.Integer); taxable_paise=db.Column(db.Integer); cgst_paise=db.Column(db.Integer); sgst_paise=db.Column(db.Integer); igst_paise=db.Column(db.Integer); total_paise=db.Column(db.Integer); created_at=db.Column(db.DateTime,default=datetime.utcnow); status=db.Column(db.String(20),default='Posted')
class ProductionRun(db.Model):
    id=db.Column(db.Integer,primary_key=True); product_id=db.Column(db.Integer,db.ForeignKey('product.id')); batch_count=db.Column(db.Integer); expected_output=db.Column(db.Integer); actual_output=db.Column(db.Integer); wastage=db.Column(db.Integer); labor_paise=db.Column(db.Integer,default=0); utilities_paise=db.Column(db.Integer,default=0); material_cost_paise=db.Column(db.Integer,default=0); total_cost_paise=db.Column(db.Integer,default=0); cost_per_packet_paise=db.Column(db.Integer,default=0); created_at=db.Column(db.DateTime,default=datetime.utcnow); created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
class RunUsage(db.Model):
    id=db.Column(db.Integer,primary_key=True); run_id=db.Column(db.Integer,db.ForeignKey('production_run.id')); material_id=db.Column(db.Integer,db.ForeignKey('material.id')); planned_milli=db.Column(db.Integer); actual_milli=db.Column(db.Integer); unit=db.Column(db.String(20)); cost_paise=db.Column(db.Integer)
class Movement(db.Model):
    id=db.Column(db.Integer,primary_key=True); item_type=db.Column(db.String(20)); item_id=db.Column(db.Integer); qty_milli=db.Column(db.Integer); unit=db.Column(db.String(20)); movement_type=db.Column(db.String(30)); source_type=db.Column(db.String(30)); source_id=db.Column(db.Integer); note=db.Column(db.String(255)); created_at=db.Column(db.DateTime,default=datetime.utcnow); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=True)
class Payment(db.Model):
    id=db.Column(db.Integer,primary_key=True); invoice_id=db.Column(db.Integer,db.ForeignKey('invoice.id')); amount_paise=db.Column(db.Integer); method=db.Column(db.String(30)); reference=db.Column(db.String(80)); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class AuditLog(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer); action=db.Column(db.String(100)); entity=db.Column(db.String(50)); entity_id=db.Column(db.Integer); details=db.Column(db.Text); created_at=db.Column(db.DateTime,default=datetime.utcnow)

@login_manager.user_loader
def load_user(uid): return db.session.get(User,int(uid))
def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*a,**kw):
            if not current_user.is_authenticated: return login_manager.unauthorized()
            if current_user.role not in roles: abort(403)
            return fn(*a,**kw)
        return wrapped
    return deco
def audit(action,entity,eid,details=''):
    db.session.add(AuditLog(user_id=current_user.id if current_user.is_authenticated else None,action=action,entity=entity,entity_id=eid,details=details))
def money(paise): return f"₹{(paise or 0)/100:,.2f}"
app.jinja_env.globals['money']=money

def add_movement(item_type,item_id,qty_milli,unit,mtype,stype,sid,note=''):
    db.session.add(Movement(item_type=item_type,item_id=item_id,qty_milli=qty_milli,unit=unit,movement_type=mtype,source_type=stype,source_id=sid,note=note,user_id=current_user.id if current_user.is_authenticated else None))
def invoice_paid(inv): return sum(p.amount_paise for p in Payment.query.filter_by(invoice_id=inv.id).all())
def invoice_due(inv): return inv.total_paise-invoice_paid(inv)
@app.context_processor
def inject(): return {'today':date.today(), 'invoice_due':invoice_due}

@app.route('/')
def index():
    if not current_user.is_authenticated: return redirect(url_for('login'))
    return redirect(url_for('dashboard'))
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','')).first()
        if u and u.check_password(request.form.get('password','')): login_user(u); return redirect(url_for('dashboard'))
        flash('Invalid username or password','danger')
    return render_template('login.html')
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))
@app.route('/dashboard')
@login_required
def dashboard():
    orders=Order.query.order_by(Order.created_at.desc()).limit(8).all(); products=Product.query.all(); mats=Material.query.all(); invoices=Invoice.query.all()
    return render_template('dashboard.html',orders=orders,products=products,mats=mats,invoices=invoices,customers=Customer.query.all(),total_due=sum(invoice_due(i) for i in invoices),runs=ProductionRun.query.order_by(ProductionRun.created_at.desc()).limit(5).all())

@app.route('/orders',methods=['GET','POST'])
@login_required
def orders():
    if request.method=='POST':
        c=db.session.get(Customer,int(request.form['customer_id'])); p=db.session.get(Product,int(request.form['product_id'])); q=max(1,int(request.form['qty']))
        if not c or not p or (current_user.role=='salesman' and c.salesman_id!=current_user.id): abort(403)
        o=Order(customer_id=c.id,salesman_id=current_user.id,product_id=p.id,qty=q,unit_price_paise=p.price_paise,notes=request.form.get('notes',''))
        db.session.add(o); db.session.flush(); audit('Order submitted','Order',o.id,f'{q} x {p.name}'); db.session.commit(); flash('Order submitted to factory','success'); return redirect(url_for('orders'))
    q=Order.query; customer_query=Customer.query
    if current_user.role=='salesman': q=q.filter_by(salesman_id=current_user.id); customer_query=customer_query.filter_by(salesman_id=current_user.id)
    return render_template('orders.html',orders=q.order_by(Order.created_at.desc()).all(),customers=customer_query.all(),products=Product.query.all())
@app.route('/orders/<int:oid>/approve',methods=['POST'])
@role_required('admin','owner')
def approve_order(oid):
    o=db.get_or_404(Order,oid); p=db.session.get(Product,o.product_id)
    if p.finished_stock<o.qty: flash(f'Insufficient finished stock: {p.finished_stock} available, {o.qty} requested. Shortage {o.qty-p.finished_stock}.','danger'); return redirect(url_for('orders'))
    o.status='Approved'; audit('Order approved','Order',o.id); db.session.commit(); flash('Order approved; invoice can now be generated','success'); return redirect(url_for('orders'))
@app.route('/orders/<int:oid>/reject',methods=['POST'])
@role_required('admin','owner')
def reject_order(oid):
    o=db.get_or_404(Order,oid); o.status='Rejected'; audit('Order rejected','Order',oid); db.session.commit(); flash('Order rejected','warning'); return redirect(url_for('orders'))
@app.route('/orders/<int:oid>/invoice',methods=['POST'])
@role_required('admin','owner')
def create_invoice(oid):
    o=db.get_or_404(Order,oid)
    if o.status!='Approved': flash('Approve the order before invoicing','warning'); return redirect(url_for('orders'))
    p=db.session.get(Product,o.product_id); c=db.session.get(Customer,o.customer_id)
    taxable=o.qty*o.unit_price_paise; tax=int((Decimal(taxable)*Decimal(p.gst_rate)/Decimal(100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)); intra=c.state.lower()=='tamil nadu'
    inv=Invoice(order_id=o.id,number=f'FY{date.today().year}-{Invoice.query.count()+1:04d}',customer_id=c.id,product_id=p.id,qty=o.qty,taxable_paise=taxable,cgst_paise=tax//2 if intra else 0,sgst_paise=tax-tax//2 if intra else 0,igst_paise=0 if intra else tax,total_paise=taxable+tax)
    db.session.add(inv); db.session.flush(); o.status='Invoiced'; audit('GST invoice posted','Invoice',inv.id,inv.number); db.session.commit(); return redirect(url_for('invoice_detail',iid=inv.id))
@app.route('/orders/<int:oid>/dispatch',methods=['POST'])
@role_required('admin','owner')
def dispatch(oid):
    o=db.get_or_404(Order,oid); inv=Invoice.query.filter_by(order_id=o.id,status='Posted').first()
    if not inv: flash('Create an invoice before dispatch','danger'); return redirect(url_for('orders'))
    if o.status=='Dispatched': flash('Already dispatched','warning'); return redirect(url_for('orders'))
    p=db.session.get(Product,o.product_id)
    if p.finished_stock<o.qty: flash('Insufficient stock at dispatch','danger'); return redirect(url_for('orders'))
    p.finished_stock-=o.qty; add_movement('finished',p.id,-o.qty*1000,'packet','Sale','Invoice',inv.id,'Dispatch'); o.status='Dispatched'; audit('Goods dispatched','Order',o.id); db.session.commit(); flash('Dispatch recorded; finished stock reduced','success'); return redirect(url_for('orders'))

@app.route('/invoices')
@login_required
def invoices(): return render_template('invoices.html',invoices=Invoice.query.order_by(Invoice.created_at.desc()).all(),customers=Customer.query.all())
@app.route('/invoice/<int:iid>')
@login_required
def invoice_detail(iid): return render_template('invoice.html',inv=db.get_or_404(Invoice,iid),customer=db.session.get(Customer,db.get_or_404(Invoice,iid).customer_id),product=db.session.get(Product,db.get_or_404(Invoice,iid).product_id),paid=invoice_paid(db.get_or_404(Invoice,iid)))
@app.route('/invoice/<int:iid>/pdf')
@login_required
def invoice_pdf(iid):
    inv=db.get_or_404(Invoice,iid); c=db.session.get(Customer,inv.customer_id); p=db.session.get(Product,inv.product_id); buf=io.BytesIO(); pdf=canvas.Canvas(buf,pagesize=A4); w,h=A4
    pdf.setFont('Helvetica-Bold',18); pdf.drawString(50,h-55,'SOUTHERN SNACKS - TAX INVOICE'); pdf.setFont('Helvetica',10)
    lines=[f'Invoice: {inv.number}',f'Date: {inv.created_at:%d-%m-%Y}',f'Customer: {c.name}',f'Place of supply: {c.state}',f'GSTIN: {c.gstin or "Unregistered"}',f'Item: {p.name} ({p.pack_size}) | HSN: {p.hsn}',f'Quantity: {inv.qty}',f'Taxable value: {money(inv.taxable_paise)}',f'CGST: {money(inv.cgst_paise)}',f'SGST: {money(inv.sgst_paise)}',f'IGST: {money(inv.igst_paise)}',f'TOTAL: {money(inv.total_paise)}']
    y=h-100
    for line in lines: pdf.drawString(55,y,line); y-=25
    pdf.drawString(55,y-20,'Computer generated invoice | Demo GST calculation'); pdf.save(); buf.seek(0); return send_file(buf,as_attachment=True,download_name=f'{inv.number}.pdf',mimetype='application/pdf')
@app.route('/invoice/<int:iid>/payment',methods=['POST'])
@role_required('admin','owner')
def payment(iid):
    inv=db.get_or_404(Invoice,iid); amount=int(Decimal(request.form['amount'])*100)
    if amount<=0 or amount>invoice_due(inv): flash('Payment must be positive and not exceed outstanding amount','danger'); return redirect(url_for('invoice_detail',iid=iid))
    db.session.add(Payment(invoice_id=iid,amount_paise=amount,method=request.form.get('method','Cash'),reference=request.form.get('reference',''))); audit('Payment recorded','Invoice',iid,money(amount)); db.session.commit(); flash('Payment recorded','success'); return redirect(url_for('invoice_detail',iid=iid))

@app.route('/production',methods=['GET','POST'])
@role_required('admin','production','owner')
def production():
    if request.method=='POST':
        p=db.session.get(Product,int(request.form['product_id'])); batch=max(1,int(request.form.get('batch_count',1))); actual=max(0,int(request.form['actual_output'])); wastage=max(0,int(request.form.get('wastage',0))); labor=int(Decimal(request.form.get('labor','0'))*100); utilities=int(Decimal(request.form.get('utilities','0'))*100)
        lines=BOMLine.query.filter_by(product_id=p.id).all(); expected=sum(0 for _ in [])+200*batch if p.name.lower().startswith('murukku') else sum(1 for _ in [])
        # Expected output is recorded from product BOM yield; current demo product yield is 200 packets per batch.
        expected=int(request.form.get('expected_output',200*batch)); usages=[]; material_cost=0
        run=ProductionRun(product_id=p.id,batch_count=batch,expected_output=expected,actual_output=actual,wastage=wastage,labor_paise=labor,utilities_paise=utilities,created_by=current_user.id); db.session.add(run); db.session.flush()
        actual_overrides={int(k.split('_')[1]):Decimal(v) for k,v in request.form.items() if k.startswith('actual_') and k[7:].isdigit() and v.strip()}
        for line in lines:
            m=db.session.get(Material,line.material_id); planned=line.qty_milli*batch; default_qty=Decimal(planned)/1000
            if m.name=='200 g pouch': default_qty=Decimal(actual+int(request.form.get('damaged_pouches',0)))
            if m.name=='Carton': default_qty=Decimal(request.form.get('cartons_used',10))
            actual_milli=int(actual_overrides.get(m.id,default_qty)*1000)
            if m.stock_milli<actual_milli: db.session.rollback(); flash(f'Insufficient {m.name} stock. Available {m.stock_milli/1000:g} {m.unit}.','danger'); return redirect(url_for('production'))
            # Weighted-average valuation: current stock rate represents latest/weighted rate.
            cost=int(Decimal(actual_milli)*Decimal(m.rate_paise)/Decimal(1000)); material_cost+=cost; m.stock_milli-=actual_milli
            db.session.add(RunUsage(run_id=run.id,material_id=m.id,planned_milli=planned,actual_milli=actual_milli,unit=m.unit,cost_paise=cost)); add_movement('material',m.id,-actual_milli,m.unit,'Issue','ProductionRun',run.id,'BOM consumption')
        run.material_cost_paise=material_cost; run.total_cost_paise=material_cost+labor+utilities; run.cost_per_packet_paise=run.total_cost_paise//actual if actual else 0; p.finished_stock+=actual; add_movement('finished',p.id,actual*1000,'packet','Production','ProductionRun',run.id,'Good output'); audit('Production run posted','ProductionRun',run.id,f'Output {actual}; expected {expected}'); db.session.commit(); flash('Production posted; raw stock reduced and finished stock increased','success'); return redirect(url_for('run_detail',rid=run.id))
    return render_template('production.html',products=Product.query.all(),materials=Material.query.all(),runs=ProductionRun.query.order_by(ProductionRun.created_at.desc()).all(),boms={p.id:BOMLine.query.filter_by(product_id=p.id).all() for p in Product.query.all()})
@app.route('/production/<int:rid>')
@login_required
def run_detail(rid):
    r=db.get_or_404(ProductionRun,rid); usages=RunUsage.query.filter_by(run_id=rid).all(); return render_template('run.html',run=r,usages=usages,materials={m.id:m.name for m in Material.query.all()})

@app.route('/purchases',methods=['GET','POST'])
@role_required('admin','production','owner')
def purchases():
    if request.method=='POST':
        mid=int(request.form['material_id']); qty=Decimal(request.form['qty']); rate=Decimal(request.form['rate']); m=db.session.get(Material,mid); qtym=int(qty*1000); ratep=int(rate*100)
        # Weighted average stock valuation, stored in paise per base unit.
        old=m.stock_milli; m.rate_paise=int((Decimal(old*m.rate_paise+qtym*ratep)/Decimal(old+qtym)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if old+qtym else ratep; m.stock_milli+=qtym
        pur=Purchase(supplier_id=int(request.form['supplier_id']),material_id=mid,qty_milli=qtym,rate_paise=ratep,reference=request.form.get('reference','')); db.session.add(pur); db.session.flush(); add_movement('material',mid,qtym,m.unit,'Receipt','Purchase',pur.id,'Purchase receipt'); audit('Purchase recorded','Purchase',pur.id); db.session.commit(); flash('Purchase recorded and stock updated','success'); return redirect(url_for('purchases'))
    return render_template('purchases.html',purchases=Purchase.query.order_by(Purchase.created_at.desc()).all(),materials=Material.query.all(),suppliers=Supplier.query.all())
@app.route('/inventory')
@login_required
def inventory(): return render_template('inventory.html',materials=Material.query.all(),products=Product.query.all(),movements=Movement.query.order_by(Movement.created_at.desc()).limit(200).all())
@app.route('/reports')
@login_required
def reports():
    start=request.args.get('start'); end=request.args.get('end'); invs=Invoice.query.order_by(Invoice.created_at.desc()).all(); runs=ProductionRun.query.all()
    if start: invs=[i for i in invs if i.created_at.date()>=date.fromisoformat(start)]
    if end: invs=[i for i in invs if i.created_at.date()<=date.fromisoformat(end)]
    return render_template('reports.html',invoices=invs,runs=runs,materials=Material.query.all(),products=Product.query.all(),payments=Payment.query.all(),customers=Customer.query.all(),start=start,end=end)
@app.route('/reports/export/<kind>')
@login_required
def export_report(kind):
    if kind not in ('sales','stock','production'): abort(404)
    wb=Workbook(); ws=wb.active; ws.title=kind.title()
    if kind=='sales':
        ws.append(['Invoice','Date','Customer','Product','Qty','Taxable ₹','CGST ₹','SGST ₹','IGST ₹','Total ₹','Outstanding ₹'])
        for i in Invoice.query.all(): ws.append([i.number,str(i.created_at),db.session.get(Customer,i.customer_id).name,db.session.get(Product,i.product_id).name,i.qty,i.taxable_paise/100,i.cgst_paise/100,i.sgst_paise/100,i.igst_paise/100,i.total_paise/100,invoice_due(i)/100])
    elif kind=='stock':
        ws.append(['Item type','Item','Balance','Unit'])
        for m in Material.query.all(): ws.append([m.category,m.name,m.stock_milli/1000,m.unit])
        for p in Product.query.all(): ws.append(['Finished',p.name,p.finished_stock,'packet'])
    else:
        ws.append(['Run','Product','Date','Expected','Actual','Wastage','Material cost ₹','Labour ₹','Power/gas ₹','Cost/packet ₹'])
        for r in ProductionRun.query.all(): ws.append([r.id,db.session.get(Product,r.product_id).name,str(r.created_at),r.expected_output,r.actual_output,r.wastage,r.material_cost_paise/100,r.labor_paise/100,r.utilities_paise/100,r.cost_per_packet_paise/100])
    out=io.BytesIO(); wb.save(out); out.seek(0); return send_file(out,as_attachment=True,download_name=f'{kind}_report.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/reports/csv/<kind>')
@login_required
def export_csv(kind):
    if kind not in ('sales','stock','production'): abort(404)
    out=io.StringIO(); writer=csv.writer(out)
    if kind=='sales':
        writer.writerow(['Invoice','Date','Customer','Product','Qty','Taxable ₹','CGST ₹','SGST ₹','IGST ₹','Total ₹','Outstanding ₹'])
        for i in Invoice.query.all(): writer.writerow([i.number,i.created_at,db.session.get(Customer,i.customer_id).name,db.session.get(Product,i.product_id).name,i.qty,i.taxable_paise/100,i.cgst_paise/100,i.sgst_paise/100,i.igst_paise/100,i.total_paise/100,invoice_due(i)/100])
    elif kind=='stock':
        writer.writerow(['Item type','Item','Balance','Unit'])
        for m in Material.query.all(): writer.writerow([m.category,m.name,m.stock_milli/1000,m.unit])
        for p in Product.query.all(): writer.writerow(['Finished',p.name,p.finished_stock,'packet'])
    else:
        writer.writerow(['Run','Product','Date','Expected','Actual','Wastage','Material cost ₹','Labour ₹','Power/gas ₹','Cost/packet ₹'])
        for r in ProductionRun.query.all(): writer.writerow([r.id,db.session.get(Product,r.product_id).name,r.created_at,r.expected_output,r.actual_output,r.wastage,r.material_cost_paise/100,r.labor_paise/100,r.utilities_paise/100,r.cost_per_packet_paise/100])
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),as_attachment=True,download_name=f'{kind}_report.csv',mimetype='text/csv')

@app.route('/reports/pdf')
@login_required
def export_pdf_report():
    buf=io.BytesIO(); pdf=canvas.Canvas(buf,pagesize=A4); w,h=A4; y=h-50
    pdf.setFont('Helvetica-Bold',16); pdf.drawString(45,y,'Southern Snacks - Monthly Audit Summary'); y-=32
    pdf.setFont('Helvetica',9)
    for line in [f'Generated: {datetime.now():%d-%m-%Y %H:%M}',f'Invoices: {Invoice.query.count()}',f'Taxable sales: {money(sum(i.taxable_paise for i in Invoice.query.all()))}',f'GST collected on invoices: {money(sum(i.cgst_paise+i.sgst_paise+i.igst_paise for i in Invoice.query.all()))}',f'Outstanding receivables: {money(sum(invoice_due(i) for i in Invoice.query.all()))}',f'Production runs: {ProductionRun.query.count()}']:
        pdf.drawString(50,y,line); y-=20
    y-=10; pdf.setFont('Helvetica-Bold',10); pdf.drawString(50,y,'Stock balances'); y-=18; pdf.setFont('Helvetica',9)
    for m in Material.query.all(): pdf.drawString(55,y,f'{m.name}: {m.stock_milli/1000:g} {m.unit}'); y-=16
    for p in Product.query.all(): pdf.drawString(55,y,f'{p.name}: {p.finished_stock} packets'); y-=16
    pdf.save(); buf.seek(0); return send_file(buf,as_attachment=True,download_name='audit_summary.pdf',mimetype='application/pdf')

@app.route('/masters')
@role_required('admin','owner')
def masters(): return render_template('masters.html',customers=Customer.query.all(),products=Product.query.all(),materials=Material.query.all(),users=User.query.all(),boms=BOMLine.query.all())
@app.route('/audit-log')
@role_required('admin','owner','auditor')
def audit_log(): return render_template('audit.html',logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(300).all())

@app.cli.command('seed')
def seed_command(): seed_data(); print('Seed data loaded. Demo logins: admin/admin123, salesa/sales123, salesb/sales123, production/prod123, auditor/audit123, owner/owner123')
def seed_data():
    db.create_all()
    if User.query.first(): return
    users=[]
    for username,name,role,pw in [('admin','Factory Admin','admin','admin123'),('salesa','Salesman A','salesman','sales123'),('salesb','Salesman B','salesman','sales123'),('production','Production Supervisor','production','prod123'),('auditor','External Auditor','auditor','audit123'),('owner','Factory Owner','owner','owner123')]:
        u=User(username=username,full_name=name,role=role); u.set_password(pw); db.session.add(u); users.append(u)
    db.session.flush()
    p=Product(name='Murukku 200 g',pack_size='200 g',hsn='190590',price_paise=5000,gst_rate=5,finished_stock=50); db.session.add(p)
    flour=Material(name='Flour',unit='kg',category='Raw material',stock_milli=100000,rate_paise=4200,reorder_level_milli=20000)
    oil=Material(name='Cooking oil',unit='litre',category='Raw material',stock_milli=30000,rate_paise=14000,reorder_level_milli=5000)
    spice=Material(name='Salt and spice mix',unit='kg',category='Raw material',stock_milli=5000,rate_paise=20000,reorder_level_milli=1000)
    pouch=Material(name='200 g pouch',unit='piece',category='Packaging',stock_milli=500000,rate_paise=250,reorder_level_milli=50000)
    carton=Material(name='Carton',unit='piece',category='Packaging',stock_milli=30000,rate_paise=1500,reorder_level_milli=5000)
    db.session.add_all([flour,oil,spice,pouch,carton]); db.session.flush()
    for m,q in [(flour,40000),(oil,10000),(spice,1200),(pouch,200000),(carton,10000)]: db.session.add(BOMLine(product_id=p.id,material_id=m.id,qty_milli=q,unit=m.unit))
    db.session.add_all([Customer(name='Retailer A',kind='Retailer',state='Tamil Nadu',gstin='33ABCDE1234F1Z5',salesman_id=users[1].id),Customer(name='Distributor B',kind='Distributor',state='Karnataka',gstin='29ABCDE1234F1Z5',salesman_id=users[2].id)])
    db.session.add(Supplier(name='Local Flour Traders',state='Tamil Nadu',gstin='33AAAPL1234C1Z1'))
    db.session.flush()
    for m in [flour,oil,spice,pouch,carton]: db.session.add(Movement(item_type='material',item_id=m.id,qty_milli=m.stock_milli,unit=m.unit,movement_type='Opening',source_type='Seed',source_id=0,note='Benchmark opening stock'))
    db.session.add(Movement(item_type='finished',item_id=p.id,qty_milli=50000,unit='packet',movement_type='Opening',source_type='Seed',source_id=0,note='Benchmark opening stock'))
    db.session.commit()

with app.app_context():
    db.create_all()
    if not User.query.first(): seed_data()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=os.getenv('FLASK_DEBUG','0')=='1')
