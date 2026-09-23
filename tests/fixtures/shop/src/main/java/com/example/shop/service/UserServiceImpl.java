package com.example.shop.service;

import com.example.shop.dto.UserDTO;
import com.example.shop.entity.User;
import com.example.shop.exception.UserNotFoundException;
import com.example.shop.repository.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.Comparator;
import java.util.List;

@Service
@Transactional(readOnly = true)
public class UserServiceImpl implements UserService {

    private static final Comparator<UserDTO> BY_NAME = (a, b) -> {
        return a.name().compareTo(b.name());
    };

    private final UserRepository userRepository;

    public UserServiceImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public List<UserDTO> findAll() {
        return userRepository.findAll().stream()
                .map(u -> new UserDTO(u.getId(), "x"))
                .sorted(BY_NAME)
                .toList();
    }

    @Override
    public UserDTO findById(Long id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new UserNotFoundException(id));
        return new UserDTO(user.getId(), "x");
    }

    @Transactional
    public <T extends Comparable<T>> UserDTO updateUser(final Long id, UserDTO dto, String... tags)
            throws IllegalStateException, UserNotFoundException {
        if (id == null) { throw new IllegalStateException("}"); }
        return dto;
    }
}
