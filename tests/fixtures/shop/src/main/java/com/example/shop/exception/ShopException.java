package com.example.shop.exception;

public abstract class ShopException extends RuntimeException {
    protected ShopException(String message) {
        super(message);
    }
}
