import pytest
from flask import session

def test_login_page_renders(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Sign In" in response.data

def test_login_success(client):
    response = client.post('/login', data={
        'identifier': 'testadmin',
        'password': 'AdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back, testadmin" in response.data

def test_login_invalid_password(client):
    response = client.post('/login', data={
        'identifier': 'testadmin',
        'password': 'WrongPassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid username/email or password" in response.data

def test_login_unregistered_user_redirects_to_register(client):
    response = client.post('/login', data={
        'identifier': 'nonexistentuser99',
        'password': 'SomePassword123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Account not found" in response.data

def test_registration_success(client):
    response = client.post('/register', data={
        'name': 'New User',
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful" in response.data

def test_registration_duplicate_username(client):
    response = client.post('/register', data={
        'name': 'Test Admin',
        'username': 'testadmin',
        'email': 'unique@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Username is already taken" in response.data

def test_logout(admin_client):
    response = admin_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been logged out" in response.data

def test_update_profile_info(admin_client):
    response = admin_client.post('/profile', data={
        'action_type': 'update_profile',
        'name': 'Updated Admin Name',
        'email': 'updatedadmin@example.com'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Profile details updated successfully" in response.data
    assert b"Updated Admin Name" in response.data

def test_change_password_success(admin_client):
    response = admin_client.post('/profile', data={
        'action_type': 'change_password',
        'current_password': 'AdminPass123',
        'password': 'NewAdminPass123',
        'confirm_password': 'NewAdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Password changed successfully" in response.data

def test_change_password_invalid_current(admin_client):
    response = admin_client.post('/profile', data={
        'action_type': 'change_password',
        'current_password': 'WrongCurrentPassword',
        'password': 'NewAdminPass123',
        'confirm_password': 'NewAdminPass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Current password is incorrect" in response.data
