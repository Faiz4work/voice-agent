"""Public demo endpoints and authenticated staff operations."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from config import setting
from ai_provider import ai_ready, chat_provider
from security import require_admin, rate_limit
from models import SessionLocal
from reception_models import Appointment, Inquiry
from reception import BUSINESSES, BookingInput, InquiryInput, availability, book, business, inquire, booking_result
from chatbot import ChatInput, chat

router = APIRouter(prefix='/api')

@router.get('/businesses')
def profiles():
    return {'data':[dict(id=key, **value) for key,value in BUSINESSES.items()]}

@router.get('/config/{business_id}')
def public_config(business_id: str):
    business(business_id)
    assistant = setting('VAPI_HVAC_ASSISTANT_ID' if business_id == 'hvac' else 'VAPI_ASSISTANT_ID')
    public_key = setting('VAPI_PUBLIC_KEY')
    ready = bool(assistant and public_key and setting('VAPI_WEBHOOK_SECRET'))
    return {'data':{'chat_mode':'ai' if ai_ready() else 'guided','voice_enabled':ready,'vapi_public_key':public_key if ready else '', 'assistant_id':assistant if ready else '', 'voice_message':'Ready to connect' if ready else 'Voice demo awaits Vapi setup. Chat and booking are available.'}}

@router.get('/{business_id}/availability')
def slots(business_id: str, date: date, service_id: str):
    return {'data':availability(business_id, date, service_id)}

@router.post('/{business_id}/bookings', status_code=201)
def booking(business_id: str, payload: BookingInput, request: Request):
    rate_limit(request, 'bookings', 10)
    return {'data':book(business_id, payload)}

@router.post('/{business_id}/inquiries', status_code=201)
def inquiry(business_id: str, payload: InquiryInput, request: Request):
    rate_limit(request, 'inquiries', 8)
    return {'data':inquire(business_id, payload)}

@router.post('/{business_id}/chat')
async def conversation(business_id: str, payload: ChatInput, request: Request):
    rate_limit(request, 'chat', 20)
    return {'data':await chat(business_id, payload)}

@router.get('/admin/{business_id}/bookings', dependencies=[Depends(require_admin)])
def staff_bookings(business_id: str):
    business(business_id)
    with SessionLocal() as db:
        rows = db.scalars(select(Appointment).where(Appointment.business_id == business_id).order_by(Appointment.starts_at).limit(200))
        return {'data':[dict(booking_result(row), customer_name=row.customer_name, phone=row.phone, email=row.email, address=row.address) for row in rows]}

@router.delete('/admin/{business_id}/bookings/{booking_id}', dependencies=[Depends(require_admin)])
def cancel_booking(business_id: str, booking_id: str):
    business(business_id)
    with SessionLocal() as db:
        row = db.get(Appointment, booking_id)
        if not row or row.business_id != business_id:
            raise HTTPException(404, 'Appointment not found')
        row.status = 'cancelled'
        row.active_slot = None
        db.commit()
        return {'data':booking_result(row)}

@router.get('/admin/{business_id}/inquiries', dependencies=[Depends(require_admin)])
def staff_inquiries(business_id: str):
    business(business_id)
    with SessionLocal() as db:
        rows = db.scalars(select(Inquiry).where(Inquiry.business_id == business_id).order_by(Inquiry.created_at.desc()).limit(200))
        return {'data':[{key:getattr(row,key) for key in ('id','customer_name','phone','message','status','created_at')} for row in rows]}
