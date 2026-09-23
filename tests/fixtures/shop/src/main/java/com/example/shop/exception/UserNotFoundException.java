package com.example.shop.exception;

public class UserNotFoundException extends ShopException {
    public UserNotFoundException(Long id) {
        super("Usuario no encontrado: " + id);
    }
}
