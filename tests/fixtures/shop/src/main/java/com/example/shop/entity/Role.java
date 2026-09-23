package com.example.shop.entity;

public enum Role {
    ADMIN("Administrador"),
    CUSTOMER("Cliente") {
        @Override
        public boolean canBuy() { return true; }
    },
    GUEST("Invitado");

    private final String label;

    Role(String label) {
        this.label = label;
    }

    public boolean canBuy() {
        return false;
    }
}
